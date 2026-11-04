//! Loading YAML entries from `entries/{data,tools}/*.yaml`.

use anyhow::{Context, Result};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

/// Sub-directories of the entries dir and the `kind` each must contain.
pub const KIND_DIRS: &[(&str, &str)] = &[("data", "data"), ("tools", "tool")];

/// One entry file as loaded from disk.
#[derive(Debug, Clone)]
pub struct EntryFile {
    pub path: PathBuf,
    /// File name without `.yaml`.
    pub stem: String,
    /// The `kind` implied by the directory the file sits in.
    pub dir_kind: &'static str,
    /// Parsed YAML as JSON, or the parse error message.
    pub value: Result<Value, String>,
}

impl EntryFile {
    pub fn display(&self) -> String {
        self.path.display().to_string()
    }
}

/// Convert YAML text into a JSON value (YAML must be a mapping at the top level).
pub fn parse_yaml(text: &str) -> Result<Value, String> {
    let yaml: serde_norway::Value = serde_norway::from_str(text).map_err(|e| e.to_string())?;
    let json = serde_json::to_value(yaml).map_err(|e| e.to_string())?;
    if !json.is_object() {
        return Err("top level of an entry must be a mapping".into());
    }
    Ok(json)
}

/// Load every `*.yaml` / `*.yml` under the known kind directories, sorted by path.
/// Files elsewhere in the entries dir are reported by the validator, not loaded.
pub fn load_dir(dir: &Path) -> Result<Vec<EntryFile>> {
    if !dir.is_dir() {
        anyhow::bail!("entries directory {} does not exist", dir.display());
    }
    let mut out = Vec::new();
    for (sub, kind) in KIND_DIRS {
        let d = dir.join(sub);
        if !d.is_dir() {
            continue;
        }
        let mut paths: Vec<PathBuf> = fs::read_dir(&d)
            .with_context(|| format!("reading {}", d.display()))?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| {
                p.is_file()
                    && matches!(
                        p.extension().and_then(|e| e.to_str()),
                        Some("yaml") | Some("yml")
                    )
            })
            .collect();
        paths.sort();
        for path in paths {
            let stem = path
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or_default()
                .to_string();
            let value = fs::read_to_string(&path)
                .map_err(|e| e.to_string())
                .and_then(|t| parse_yaml(&t));
            out.push(EntryFile {
                path,
                stem,
                dir_kind: kind,
                value,
            });
        }
    }
    Ok(out)
}

/// Return only the successfully parsed entries (used after validation passed).
pub fn values(files: &[EntryFile]) -> Vec<Value> {
    files
        .iter()
        .filter_map(|f| f.value.as_ref().ok().cloned())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_mapping() {
        let v = parse_yaml("id: a\nkind: tool\n").unwrap();
        assert_eq!(v["id"], "a");
    }

    #[test]
    fn rejects_non_mapping() {
        assert!(parse_yaml("- a\n- b\n").is_err());
        assert!(parse_yaml("id: [unclosed\n").is_err());
    }

    #[test]
    fn dates_stay_strings() {
        let v = parse_yaml("last_verified: 2026-01-02\n").unwrap();
        assert_eq!(v["last_verified"], "2026-01-02");
    }
}
