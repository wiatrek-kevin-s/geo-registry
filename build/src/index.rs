//! Building the published index: `index.json`, `registry.sqlite`, `index.sha256`.

use crate::entries::kind_of;
use crate::FORMAT_VERSION;
use anyhow::{Context, Result};
use rusqlite::{params, Connection};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

/// Paths of the files a build writes.
#[derive(Debug)]
pub struct BuildOutput {
    pub index_json: PathBuf,
    pub sqlite: PathBuf,
    pub sha256: PathBuf,
    /// Data and tool entries (the `entries` table / list).
    pub count: usize,
    pub operations: usize,
    pub implementations: usize,
}

/// True for the kinds Columbus reads from `entries` today (data and tool).
/// Operations and implementations are published in their own tables, so
/// existing readers of the index see exactly what they saw before.
pub fn is_catalogue(entry: &Value) -> bool {
    !matches!(kind_of(entry), Some("operation") | Some("implementation"))
}

fn sorted_by_id<'a>(entries: impl Iterator<Item = &'a Value>) -> Vec<&'a Value> {
    let mut v: Vec<&Value> = entries.collect();
    v.sort_by_key(|e| str_field(e, "id").unwrap_or_default().to_string());
    v
}

/// The card for an operation: what it is, its other names and which
/// Columbus tool runs it today.
pub fn operation_card(entry: &Value) -> Value {
    let mut c = Map::new();
    for key in ["id", "kind", "name", "summary", "group"] {
        c.insert(
            key.into(),
            Value::String(str_field(entry, key).unwrap_or_default().into()),
        );
    }
    for key in ["aka", "columbus", "checks"] {
        if let Some(v) = entry.get(key) {
            c.insert(key.into(), v.clone());
        }
    }
    c.insert(
        "status".into(),
        Value::String(str_field(entry, "status").unwrap_or("active").into()),
    );
    if let Some(r) = entry.pointer("/review/state") {
        c.insert("review".into(), r.clone());
    }
    Value::Object(c)
}

/// The card for an implementation: which engine, how it is called, which
/// operation it implements (if mapped) and the engine version harvested.
pub fn implementation_card(entry: &Value) -> Value {
    let mut c = Map::new();
    for key in ["id", "kind", "name", "software", "implements"] {
        if let Some(v) = str_field(entry, key) {
            c.insert(key.into(), Value::String(v.into()));
        }
    }
    for key in ["call", "docs"] {
        if let Some(v) = entry.get(key) {
            c.insert(key.into(), v.clone());
        }
    }
    if let Some(v) = entry.pointer("/harvest/engine_version") {
        c.insert("engine_version".into(), v.clone());
    }
    c.insert(
        "status".into(),
        Value::String(str_field(entry, "status").unwrap_or("active").into()),
    );
    if let Some(r) = entry.pointer("/review/state") {
        c.insert("review".into(), r.clone());
    }
    Value::Object(c)
}

/// Searchable text for an implementation: its parameter names and the
/// operation it implements.
fn implementation_terms(entry: &Value) -> String {
    let mut parts: Vec<String> = Vec::new();
    if let Some(p) = entry.get("parameters").and_then(Value::as_object) {
        parts.extend(p.keys().map(|k| k.replace(['_', '-'], " ")));
    }
    if let Some(op) = str_field(entry, "implements") {
        parts.push(op.replace('-', " "));
    }
    parts.join(" ")
}

/// Searchable text for an operation besides its name and summary: other
/// names, parameter names and input/output types.
fn operation_terms(entry: &Value) -> String {
    let mut parts: Vec<String> = Vec::new();
    if let Some(a) = entry.get("aka").and_then(Value::as_array) {
        parts.extend(a.iter().filter_map(Value::as_str).map(str::to_string));
    }
    if let Some(p) = entry.get("parameters").and_then(Value::as_object) {
        parts.extend(p.keys().map(|k| k.replace('_', " ")));
    }
    for ports in ["inputs", "outputs"] {
        if let Some(list) = entry.get(ports).and_then(Value::as_array) {
            for port in list {
                for k in ["type", "geometry"] {
                    if let Some(s) = port.get(k).and_then(Value::as_str) {
                        parts.push(s.to_string());
                    }
                }
            }
        }
    }
    if let Some(op) = entry.pointer("/columbus/op").and_then(Value::as_str) {
        parts.push(op.replace('_', " "));
    }
    parts.join(" ")
}

fn str_field<'a>(v: &'a Value, key: &str) -> Option<&'a str> {
    v.get(key).and_then(Value::as_str)
}

/// The compact card shown in search results and in `index.json`.
pub fn card(entry: &Value) -> Value {
    let mut c = Map::new();
    for key in ["id", "kind", "name", "summary"] {
        c.insert(
            key.into(),
            Value::String(str_field(entry, key).unwrap_or_default().into()),
        );
    }
    if let Some(t) = entry.get("themes") {
        c.insert("themes".into(), t.clone());
    }
    if let Some(cat) = str_field(entry, "category") {
        c.insert("category".into(), Value::String(cat.into()));
    }
    if let Some(sub) = str_field(entry, "subcategory") {
        c.insert("subcategory".into(), Value::String(sub.into()));
    }
    if let Some(r) = entry.pointer("/coverage/region") {
        c.insert("region".into(), r.clone());
    }
    c.insert(
        "license".into(),
        Value::String(str_field(entry, "license").unwrap_or("NOASSERTION").into()),
    );
    let access_types: Vec<Value> = entry
        .get("access")
        .and_then(Value::as_array)
        .map(|a| {
            let mut seen = Vec::new();
            for t in a.iter().filter_map(|x| x.get("type").cloned()) {
                if !seen.contains(&t) {
                    seen.push(t);
                }
            }
            seen
        })
        .unwrap_or_default();
    if !access_types.is_empty() {
        c.insert("access_types".into(), Value::Array(access_types));
    }
    c.insert(
        "status".into(),
        Value::String(str_field(entry, "status").unwrap_or("active").into()),
    );
    let url =
        str_field(entry, "url").or_else(|| entry.pointer("/access/0/url").and_then(Value::as_str));
    if let Some(u) = url {
        c.insert("url".into(), Value::String(u.into()));
    }
    if let Some(r) = entry.pointer("/review/state") {
        c.insert("review".into(), r.clone());
    }
    Value::Object(c)
}

/// Text that goes into the FTS `themes` column: data themes, or a tool's
/// subcategory, atlas kind and interfaces, so "raster"/"python" etc. match.
fn themes_text(entry: &Value) -> String {
    let mut parts: Vec<String> = Vec::new();
    for key in ["themes", "interfaces", "also_categories", "formats_out"] {
        if let Some(a) = entry.get(key).and_then(Value::as_array) {
            parts.extend(
                a.iter()
                    .filter_map(Value::as_str)
                    .map(|s| s.replace('-', " ")),
            );
        }
    }
    for key in ["subcategory", "tool_kind", "publisher"] {
        if let Some(s) = str_field(entry, key) {
            parts.push(s.to_string());
        }
    }
    if let Some(r) = entry.pointer("/coverage/region").and_then(Value::as_str) {
        parts.push(r.to_string());
    }
    parts.join(" ")
}

/// RFC 3339 UTC timestamp. Honours `SOURCE_DATE_EPOCH` for reproducible builds.
pub fn generated_at() -> String {
    let secs = std::env::var("SOURCE_DATE_EPOCH")
        .ok()
        .and_then(|s| s.parse::<i64>().ok())
        .unwrap_or_else(|| {
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs() as i64)
                .unwrap_or(0)
        });
    format_rfc3339(secs)
}

/// Format seconds since the Unix epoch as `YYYY-MM-DDTHH:MM:SSZ`.
pub fn format_rfc3339(secs: i64) -> String {
    let days = secs.div_euclid(86_400);
    let rem = secs.rem_euclid(86_400);
    // Howard Hinnant's civil_from_days.
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!(
        "{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z",
        rem / 3600,
        (rem % 3600) / 60,
        rem % 60
    )
}

/// Build `index.json` contents (entries sorted by id).
/// `entries` and `count` hold data and tool entries only, as before;
/// operations follow in their own list.
pub fn index_json(entries: &[Value], generated_at: &str) -> Value {
    let cards: Vec<Value> = sorted_by_id(entries.iter().filter(|e| is_catalogue(e)))
        .into_iter()
        .map(card)
        .collect();
    let ops: Vec<Value> = sorted_by_id(entries.iter().filter(|e| kind_of(e) == Some("operation")))
        .into_iter()
        .map(operation_card)
        .collect();
    json!({
        "format_version": FORMAT_VERSION,
        "generated_at": generated_at,
        "count": cards.len(),
        "entries": cards,
        "operations_count": ops.len(),
        "operations": ops,
    })
}

/// Create the SQLite database at `path` (replacing any existing file).
pub fn write_sqlite(path: &Path, entries: &[Value], generated_at: &str) -> Result<()> {
    if path.exists() {
        fs::remove_file(path).with_context(|| format!("removing old {}", path.display()))?;
    }
    let mut conn =
        Connection::open(path).with_context(|| format!("creating {}", path.display()))?;
    conn.execute_batch(
        "PRAGMA journal_mode = DELETE;
         CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
         CREATE TABLE entries (
             id     TEXT PRIMARY KEY,
             kind   TEXT NOT NULL CHECK (kind IN ('data', 'tool')),
             name   TEXT NOT NULL,
             status TEXT NOT NULL,
             card   TEXT NOT NULL,   -- JSON card (same as index.json)
             entry  TEXT NOT NULL    -- full entry as JSON
         );
         CREATE INDEX entries_kind ON entries(kind);
         CREATE VIRTUAL TABLE entries_fts USING fts5(
             id UNINDEXED, name, summary, category, themes, notes,
             tokenize = 'porter unicode61 remove_diacritics 2'
         );
         -- Added in format 1 without changing the tables above.
         CREATE TABLE operations (
             id     TEXT PRIMARY KEY,
             name   TEXT NOT NULL,
             status TEXT NOT NULL,
             card   TEXT NOT NULL,
             entry  TEXT NOT NULL
         );
         CREATE VIRTUAL TABLE operations_fts USING fts5(
             id UNINDEXED, name, summary, terms, notes,
             tokenize = 'porter unicode61 remove_diacritics 2'
         );
         CREATE TABLE implementations (
             id         TEXT PRIMARY KEY,
             implements TEXT,           -- operation id, or NULL if not mapped yet
             software   TEXT NOT NULL,  -- tool entry id
             name       TEXT NOT NULL,
             status     TEXT NOT NULL,
             card       TEXT NOT NULL,
             entry      TEXT NOT NULL
         );
         CREATE INDEX implementations_op ON implementations(implements);
         CREATE INDEX implementations_software ON implementations(software);
         CREATE VIRTUAL TABLE implementations_fts USING fts5(
             id UNINDEXED, name, call, software, terms,
             tokenize = 'porter unicode61 remove_diacritics 2'
         );",
    )?;
    let catalogue = sorted_by_id(entries.iter().filter(|e| is_catalogue(e)));
    let operations = sorted_by_id(entries.iter().filter(|e| kind_of(e) == Some("operation")));
    let implementations = sorted_by_id(
        entries
            .iter()
            .filter(|e| kind_of(e) == Some("implementation")),
    );
    let tx = conn.transaction()?;
    {
        let mut meta = tx.prepare("INSERT INTO meta (key, value) VALUES (?1, ?2)")?;
        meta.execute(params!["format_version", FORMAT_VERSION.to_string()])?;
        meta.execute(params!["generated_at", generated_at])?;
        meta.execute(params!["count", catalogue.len().to_string()])?;
        meta.execute(params!["operations_count", operations.len().to_string()])?;
        meta.execute(params![
            "implementations_count",
            implementations.len().to_string()
        ])?;

        let mut ins = tx.prepare(
            "INSERT INTO entries (id, kind, name, status, card, entry) VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        )?;
        let mut fts = tx.prepare(
            "INSERT INTO entries_fts (id, name, summary, category, themes, notes)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        )?;
        for e in &catalogue {
            let id = str_field(e, "id").unwrap_or_default();
            ins.execute(params![
                id,
                str_field(e, "kind").unwrap_or_default(),
                str_field(e, "name").unwrap_or_default(),
                str_field(e, "status").unwrap_or("active"),
                card(e).to_string(),
                e.to_string(),
            ])?;
            fts.execute(params![
                id,
                str_field(e, "name").unwrap_or_default(),
                str_field(e, "summary").unwrap_or_default(),
                str_field(e, "category").unwrap_or_default(),
                themes_text(e),
                str_field(e, "notes").unwrap_or_default(),
            ])?;
        }

        let mut ins = tx.prepare(
            "INSERT INTO operations (id, name, status, card, entry) VALUES (?1, ?2, ?3, ?4, ?5)",
        )?;
        let mut fts = tx.prepare(
            "INSERT INTO operations_fts (id, name, summary, terms, notes) VALUES (?1, ?2, ?3, ?4, ?5)",
        )?;
        for e in &operations {
            let id = str_field(e, "id").unwrap_or_default();
            ins.execute(params![
                id,
                str_field(e, "name").unwrap_or_default(),
                str_field(e, "status").unwrap_or("active"),
                operation_card(e).to_string(),
                e.to_string(),
            ])?;
            fts.execute(params![
                id,
                str_field(e, "name").unwrap_or_default(),
                str_field(e, "summary").unwrap_or_default(),
                operation_terms(e),
                str_field(e, "notes").unwrap_or_default(),
            ])?;
        }

        let mut ins = tx.prepare(
            "INSERT INTO implementations (id, implements, software, name, status, card, entry)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
        )?;
        let mut fts = tx.prepare(
            "INSERT INTO implementations_fts (id, name, call, software, terms)
             VALUES (?1, ?2, ?3, ?4, ?5)",
        )?;
        for e in &implementations {
            let id = str_field(e, "id").unwrap_or_default();
            ins.execute(params![
                id,
                str_field(e, "implements"),
                str_field(e, "software").unwrap_or_default(),
                str_field(e, "name").unwrap_or_default(),
                str_field(e, "status").unwrap_or("active"),
                implementation_card(e).to_string(),
                e.to_string(),
            ])?;
            let call = e
                .pointer("/call/name")
                .and_then(Value::as_str)
                .unwrap_or_default();
            fts.execute(params![
                id,
                str_field(e, "name")
                    .unwrap_or_default()
                    .replace(['_', '.', ':'], " "),
                call.replace(['_', '.', ':'], " "),
                str_field(e, "software").unwrap_or_default(),
                implementation_terms(e),
            ])?;
        }
    }
    tx.commit()?;
    conn.execute_batch(
        "INSERT INTO entries_fts(entries_fts) VALUES ('optimize');
         INSERT INTO operations_fts(operations_fts) VALUES ('optimize');
         INSERT INTO implementations_fts(implementations_fts) VALUES ('optimize');
         VACUUM;",
    )?;
    Ok(())
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|b| format!("{b:02x}")).collect()
}

/// Write all build outputs into `out`.
pub fn build(entries: &[Value], out: &Path) -> Result<BuildOutput> {
    fs::create_dir_all(out).with_context(|| format!("creating {}", out.display()))?;
    let ts = generated_at();

    let index_path = out.join("index.json");
    let mut text = serde_json::to_string_pretty(&index_json(entries, &ts))?;
    text.push('\n');
    fs::write(&index_path, &text)?;

    let db_path = out.join("registry.sqlite");
    write_sqlite(&db_path, entries, &ts)?;

    // `sha256sum -c` compatible manifest.
    // TODO(signing): sign index.sha256 (e.g. minisign or Sigstore keyless in CI) and
    // publish the signature next to it, so the Columbus server can verify the index
    // before trusting it. Until then the manifest only detects accidental corruption.
    let sha_path = out.join("index.sha256");
    let manifest = format!(
        "{}  index.json\n{}  registry.sqlite\n",
        sha256_hex(text.as_bytes()),
        sha256_hex(&fs::read(&db_path)?)
    );
    fs::write(&sha_path, manifest)?;

    Ok(BuildOutput {
        index_json: index_path,
        sqlite: db_path,
        sha256: sha_path,
        count: entries.iter().filter(|e| is_catalogue(e)).count(),
        operations: entries
            .iter()
            .filter(|e| kind_of(e) == Some("operation"))
            .count(),
        implementations: entries
            .iter()
            .filter(|e| kind_of(e) == Some("implementation"))
            .count(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rfc3339_formatting() {
        assert_eq!(format_rfc3339(0), "1970-01-01T00:00:00Z");
        assert_eq!(format_rfc3339(1_709_210_096), "2024-02-29T12:34:56Z");
        assert_eq!(format_rfc3339(951_782_400), "2000-02-29T00:00:00Z");
    }

    #[test]
    fn sha_of_empty() {
        assert_eq!(
            sha256_hex(b""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
    }

    #[test]
    fn data_card_fields() {
        let e = json!({
            "id": "d", "kind": "data", "name": "D", "summary": "S", "themes": ["lidar"],
            "coverage": {"region": "Texas"}, "license": "CC0-1.0",
            "access": [{"type": "ept", "url": "https://a"}, {"type": "ept", "url": "https://b"},
                       {"type": "http", "url": "https://c"}],
            "status": "active", "notes": "not in card"
        });
        let c = card(&e);
        assert_eq!(c["region"], "Texas");
        assert_eq!(c["access_types"], json!(["ept", "http"]));
        assert_eq!(c["url"], "https://a");
        assert!(c.get("notes").is_none());
    }

    #[test]
    fn tool_card_fields() {
        let e = json!({"id": "t", "kind": "tool", "name": "T", "category": "C",
                       "license": "MIT", "url": "https://t", "status": "active"});
        let c = card(&e);
        assert_eq!(c["category"], "C");
        assert_eq!(c["url"], "https://t");
        assert!(c.get("access_types").is_none());
    }

    #[test]
    fn operations_kept_out_of_entries() {
        let es = vec![
            json!({"id": "d", "kind": "data", "name": "D"}),
            json!({"id": "buffer", "kind": "operation", "name": "Buffer", "group": "vector/proximity",
                   "aka": ["proximity zone"], "columbus": {"tool": "vector_op", "op": "buffer"}}),
        ];
        let idx = index_json(&es, "x");
        assert_eq!(idx["count"], 1);
        assert_eq!(idx["entries"].as_array().unwrap().len(), 1);
        assert_eq!(idx["operations_count"], 1);
        assert_eq!(idx["operations"][0]["columbus"]["op"], "buffer");
        assert_eq!(idx["operations"][0]["aka"][0], "proximity zone");
    }

    #[test]
    fn index_sorted_and_counted() {
        let es = vec![json!({"id": "b"}), json!({"id": "a"})];
        let idx = index_json(&es, "x");
        assert_eq!(idx["count"], 2);
        assert_eq!(idx["entries"][0]["id"], "a");
        assert_eq!(idx["format_version"], FORMAT_VERSION);
    }
}
