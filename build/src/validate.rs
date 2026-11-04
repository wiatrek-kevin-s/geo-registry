//! Schema and cross-entry validation.

use crate::entries::EntryFile;
use crate::RECIPE_TOOLS;
use anyhow::{Context, Result};
use serde_json::Value;
use std::collections::{BTreeMap, HashSet};
use std::fmt;
use std::fs;
use std::path::Path;

/// A single readable problem tied to one file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Problem {
    pub file: String,
    pub message: String,
}

impl fmt::Display for Problem {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.file, self.message)
    }
}

/// Compile the entry schema (JSON Schema 2020-12, formats asserted).
pub fn load_schema(path: &Path) -> Result<jsonschema::Validator> {
    let text =
        fs::read_to_string(path).with_context(|| format!("reading schema {}", path.display()))?;
    let schema: Value =
        serde_json::from_str(&text).with_context(|| format!("parsing {}", path.display()))?;
    compile_schema(&schema)
}

pub fn compile_schema(schema: &Value) -> Result<jsonschema::Validator> {
    jsonschema::draft202012::options()
        .should_validate_formats(true)
        .build(schema)
        .map_err(|e| anyhow::anyhow!("invalid schema: {e}"))
}

/// Longest rendering of an offending value kept in a message.
const MAX_MESSAGE: usize = 240;

/// Validate one value against the schema, returning readable messages.
/// The schema dispatches on `kind` with if/then (not `oneOf`), so errors point
/// at the real field rather than "not valid under any of the schemas".
pub fn schema_errors(validator: &jsonschema::Validator, value: &Value) -> Vec<String> {
    let mut out: Vec<String> = validator
        .iter_errors(value)
        .map(|e| {
            let at = e.instance_path().to_string();
            let at = if at.is_empty() { "/".to_string() } else { at };
            let mut msg = e.to_string();
            if msg.chars().count() > MAX_MESSAGE {
                msg = msg.chars().take(MAX_MESSAGE).collect::<String>() + " ...";
            }
            format!("schema: at {at}: {msg}")
        })
        .collect();
    out.sort();
    out.dedup();
    out
}

/// Run the schema and all cross-entry checks. Returns every problem found.
pub fn validate_files(files: &[EntryFile], validator: &jsonschema::Validator) -> Vec<Problem> {
    let mut problems = Vec::new();
    let mut push = |file: &EntryFile, message: String| {
        problems.push(Problem {
            file: file.display(),
            message,
        })
    };

    // First pass: per-file checks and id collection.
    let mut ids: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for f in files {
        let v = match &f.value {
            Ok(v) => v,
            Err(e) => {
                push(f, format!("YAML parse error: {e}"));
                continue;
            }
        };
        for msg in schema_errors(validator, v) {
            push(f, msg);
        }
        match v.get("id").and_then(Value::as_str) {
            Some(id) => {
                if id != f.stem {
                    push(
                        f,
                        format!("id '{id}' does not match file name '{}.yaml'", f.stem),
                    );
                }
                ids.entry(id.to_string()).or_default().push(f.display());
            }
            None => push(f, "missing string field 'id'".into()),
        }
        match v.get("kind").and_then(Value::as_str) {
            Some(kind) if kind != f.dir_kind => push(
                f,
                format!(
                    "kind '{kind}' does not belong in this directory (expected '{}')",
                    f.dir_kind
                ),
            ),
            _ => {}
        }
        if let Some(tool) = v.pointer("/recipe/tool") {
            match tool.as_str() {
                Some(t) if RECIPE_TOOLS.contains(&t) => {}
                _ => push(
                    f,
                    format!(
                        "recipe.tool {tool} is not one of the allowed Columbus tools ({})",
                        RECIPE_TOOLS.join(", ")
                    ),
                ),
            }
        }
    }

    for (id, paths) in &ids {
        if paths.len() > 1 {
            problems.push(Problem {
                file: paths[1..].join(", "),
                message: format!("duplicate id '{id}' (first defined in {})", paths[0]),
            });
        }
    }

    // Second pass: references must resolve.
    let known: HashSet<&str> = ids.keys().map(String::as_str).collect();
    for f in files {
        let Ok(v) = &f.value else { continue };
        let self_id = v.get("id").and_then(Value::as_str).unwrap_or_default();
        if let Some(rel) = v.get("related").and_then(Value::as_array) {
            for r in rel {
                match r.as_str() {
                    Some(r) if r == self_id => problems.push(Problem {
                        file: f.display(),
                        message: format!("related lists the entry itself ('{r}')"),
                    }),
                    Some(r) if !known.contains(r) => problems.push(Problem {
                        file: f.display(),
                        message: format!("related id '{r}' does not resolve to any entry"),
                    }),
                    _ => {}
                }
            }
        }
        if let Some(r) = v.get("replaced_by").and_then(Value::as_str) {
            if !known.contains(r) {
                problems.push(Problem {
                    file: f.display(),
                    message: format!("replaced_by '{r}' does not resolve to any entry"),
                });
            }
        }
    }
    problems
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::path::PathBuf;

    fn schema() -> jsonschema::Validator {
        let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../schema/entry.schema.json");
        load_schema(&p).expect("schema compiles")
    }

    fn tool(id: &str) -> Value {
        json!({
            "id": id, "kind": "tool", "name": "T", "category": "C", "tool_kind": "Library",
            "open_source": "yes", "license": "MIT", "interfaces": ["Python"],
            "project_status": "active", "status": "active",
            "review": {"state": "seeded", "source": "geospatial-tool-atlas", "source_row": 2}
        })
    }

    fn data(id: &str) -> Value {
        json!({
            "id": id, "kind": "data", "name": "D", "publisher": "Unknown", "themes": ["x"],
            "coverage": {"region": "Texas"}, "license": "CC0-1.0",
            "access": [{"type": "http", "url": "https://example.org", "auth": "none"}],
            "status": "active", "review": {"state": "reviewed"}
        })
    }

    fn file(stem: &str, kind: &'static str, v: Value) -> EntryFile {
        EntryFile {
            path: PathBuf::from(format!("{stem}.yaml")),
            stem: stem.into(),
            dir_kind: kind,
            value: Ok(v),
        }
    }

    #[test]
    fn valid_entries_pass() {
        let s = schema();
        let files = vec![file("a", "tool", tool("a")), file("d", "data", data("d"))];
        assert!(validate_files(&files, &s).is_empty());
    }

    #[test]
    fn id_must_match_stem_and_be_unique() {
        let s = schema();
        let files = vec![file("a", "tool", tool("b")), file("b", "tool", tool("b"))];
        let p = validate_files(&files, &s);
        assert!(p
            .iter()
            .any(|p| p.message.contains("does not match file name")));
        assert!(p.iter().any(|p| p.message.contains("duplicate id 'b'")));
    }

    #[test]
    fn related_must_resolve() {
        let s = schema();
        let mut t = tool("a");
        t["related"] = json!(["missing"]);
        let p = validate_files(&[file("a", "tool", t)], &s);
        assert!(p
            .iter()
            .any(|p| p.message.contains("'missing' does not resolve")));
    }

    #[test]
    fn recipe_tool_restricted_and_declarative() {
        let s = schema();
        let mut d = data("d");
        d["recipe"] = json!({"tool": "run_shell", "steps": ["do it"]});
        let p = validate_files(&[file("d", "data", d.clone())], &s);
        assert!(p.iter().any(|p| p.message.contains("recipe.tool")));

        d["recipe"] = json!({"tool": "raster_op", "steps": ["clip to `rm -rf /`"]});
        assert!(!schema_errors(&s, &d).is_empty());

        d["recipe"] = json!({"tool": "raster_op", "steps": ["clip to the request bbox"]});
        assert!(schema_errors(&s, &d).is_empty());
    }

    #[test]
    fn schema_rejects_bad_values() {
        let s = schema();
        let mut d = data("d");
        d["access"][0]["type"] = json!("ftp");
        d["last_verified"] = json!("yesterday");
        let errs = schema_errors(&s, &d);
        assert!(!errs.is_empty());
        let mut t = tool("Bad_ID");
        t["open_source"] = json!("maybe");
        assert!(!schema_errors(&s, &t).is_empty());
    }

    #[test]
    fn kind_must_match_directory() {
        let s = schema();
        let p = validate_files(&[file("a", "data", tool("a"))], &s);
        assert!(p.iter().any(|p| p.message.contains("does not belong")));
    }
}
