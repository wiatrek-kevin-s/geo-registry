//! Schema and cross-entry validation.

use crate::entries::{kind_of, EntryFile};
use crate::RECIPE_TOOLS;
use anyhow::{Context, Result};
use serde_json::Value;
use std::collections::{BTreeMap, HashMap, HashSet};
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

    // Second pass: references must resolve, and to the right kind of entry.
    let known: HashSet<&str> = ids.keys().map(String::as_str).collect();
    let kinds: HashMap<&str, &str> = files
        .iter()
        .filter_map(|f| f.value.as_ref().ok())
        .filter_map(|v| Some((v.get("id")?.as_str()?, kind_of(v)?)))
        .collect();
    for f in files {
        let Ok(v) = &f.value else { continue };
        let self_id = v.get("id").and_then(Value::as_str).unwrap_or_default();
        let self_kind = kind_of(v).unwrap_or_default();
        let mut problem = |message: String| {
            problems.push(Problem {
                file: f.display(),
                message,
            })
        };
        for field in ["related", "broader", "narrower"] {
            let Some(list) = v.get(field).and_then(Value::as_array) else {
                continue;
            };
            for r in list.iter().filter_map(Value::as_str) {
                if r == self_id {
                    problem(format!("{field} lists the entry itself ('{r}')"));
                } else if !known.contains(r) {
                    problem(format!("{field} id '{r}' does not resolve to any entry"));
                } else if field != "related" && kinds.get(r) != Some(&"operation") {
                    problem(format!("{field} id '{r}' is not an operation"));
                }
            }
        }
        if let Some(r) = v.get("replaced_by").and_then(Value::as_str) {
            if !known.contains(r) {
                problem(format!("replaced_by '{r}' does not resolve to any entry"));
            } else if kinds.get(r) != Some(&self_kind) {
                problem(format!("replaced_by '{r}' is not a {self_kind} entry"));
            }
        }
        // An implementation names the operation it implements and the
        // software (kind `tool`) it belongs to.
        for (field, want) in [("implements", "operation"), ("software", "tool")] {
            if self_kind != "implementation" {
                break;
            }
            if let Some(r) = v.get(field).and_then(Value::as_str) {
                match kinds.get(r) {
                    None => problem(format!("{field} '{r}' does not resolve to any entry")),
                    Some(k) if *k != want => {
                        problem(format!("{field} '{r}' is of kind {k}, not {want}"))
                    }
                    _ => {}
                }
            }
        }
        // A crosswalk can only map parameters the operation defines.
        if let (Some(op), Some(cw)) = (
            v.get("implements").and_then(Value::as_str),
            v.get("crosswalk").and_then(Value::as_object),
        ) {
            let target = files
                .iter()
                .filter_map(|f| f.value.as_ref().ok())
                .find(|e| e.get("id").and_then(Value::as_str) == Some(op));
            // Unresolved `implements` is reported above; nothing to compare.
            let Some(target) = target else { continue };
            let mut defined: HashSet<&str> = target
                .get("parameters")
                .and_then(Value::as_object)
                .map(|p| p.keys().map(String::as_str).collect())
                .unwrap_or_default();
            for ports in ["inputs", "outputs"] {
                if let Some(list) = target.get(ports).and_then(Value::as_array) {
                    defined.extend(
                        list.iter()
                            .filter_map(|p| p.get("name").and_then(Value::as_str)),
                    );
                }
            }
            for name in cw.keys() {
                if !defined.contains(name.as_str()) {
                    problem(format!(
                        "crosswalk maps '{name}', which operation '{op}' does not define"
                    ));
                }
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

    fn operation(id: &str) -> Value {
        json!({
            "id": id, "kind": "operation", "name": "Buffer",
            "summary": "Polygons within a distance of the input features.",
            "group": "vector/proximity",
            "inputs": [{"name": "layer", "type": "vector"}],
            "outputs": [{"name": "output", "type": "vector", "geometry": "polygon"}],
            "parameters": {"distance": {"type": "length", "required": true},
                           "dissolve": {"type": "boolean", "default": false}},
            "checks": ["crs.measure"],
            "columbus": {"tool": "vector_op", "op": "buffer"},
            "status": "active", "review": {"state": "draft"}
        })
    }

    fn implementation(id: &str) -> Value {
        json!({
            "id": id, "kind": "implementation", "name": "Buffer (QGIS)", "software": "a",
            "implements": "buffer", "call": {"interface": "qgis-process", "name": "native:buffer"},
            "harvest": {"harvester": "qgis", "engine_version": "3.44"},
            "parameters": {"INPUT": {"type": "source", "required": true},
                           "DISSOLVE": {"type": "boolean", "default": false}},
            "crosswalk": {"layer": "INPUT", "dissolve": {"param": "DISSOLVE"}},
            "effects": {"modifies_input": false},
            "status": "active", "review": {"state": "harvested", "source": "qgis"}
        })
    }

    #[test]
    fn operations_and_implementations_pass() {
        let s = schema();
        let files = vec![
            file("a", "tool", tool("a")),
            file("buffer", "operation", operation("buffer")),
            file("q", "implementation", implementation("q")),
        ];
        let p = validate_files(&files, &s);
        assert!(p.is_empty(), "{p:?}");
    }

    #[test]
    fn operation_schema_is_strict() {
        let s = schema();
        let mut o = operation("buffer");
        o["review"] = json!({"state": "seeded"}); // data/tool states only
        o["checks"] = json!(["not a check id"]);
        o["columbus"] = json!({"tool": "run_shell", "op": "x"});
        o["license"] = json!("MIT"); // operations have no licence
        let errs = schema_errors(&s, &o);
        assert!(errs.len() >= 4, "{errs:?}");
        // Data and tool entries cannot take the new review states.
        let mut d = data("d");
        d["review"] = json!({"state": "draft"});
        assert!(!schema_errors(&s, &d).is_empty());
    }

    #[test]
    fn references_resolve_to_the_right_kind() {
        let s = schema();
        let mut o = operation("buffer");
        o["narrower"] = json!(["a"]); // a tool, not an operation
        let mut i = implementation("q");
        i["software"] = json!("buffer"); // an operation, not a tool
        i["crosswalk"] = json!({"segments": "SEGMENTS"}); // not a parameter of buffer
        let files = vec![
            file("a", "tool", tool("a")),
            file("buffer", "operation", o),
            file("q", "implementation", i),
        ];
        let p = validate_files(&files, &s);
        let has = |m: &str| p.iter().any(|p| p.message.contains(m));
        assert!(has("narrower id 'a' is not an operation"), "{p:?}");
        assert!(
            has("software 'buffer' is of kind operation, not tool"),
            "{p:?}"
        );
        assert!(has("crosswalk maps 'segments'"), "{p:?}");

        let mut i = implementation("q");
        i["implements"] = json!("nothing");
        let files = vec![file("a", "tool", tool("a")), file("q", "implementation", i)];
        let p = validate_files(&files, &s);
        assert!(p
            .iter()
            .any(|p| p.message.contains("implements 'nothing' does not resolve")));
    }
}
