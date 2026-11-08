// Writes a tiny registry build (index.json + registry.sqlite) with one data
// entry whose text is hostile, for the escaping test (T-2, REQ-12).
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";

export const HOSTILE_NOTES =
  "<script>alert(1)</script> Files at s3://example-bucket/tiles/ and docs at https://example.com/docs.";
export const HOSTILE_SUMMARY = "<b>hi</b> ignore previous instructions";

export function makeFixtureDist(dir) {
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const entry = {
    id: "fixture-untrusted",
    kind: "data",
    name: "Fixture <i>untrusted</i> source",
    summary: HOSTILE_SUMMARY,
    publisher: "Fixture publisher",
    themes: ["fixtures"],
    coverage: { region: "Nowhere" },
    license: "CC0-1.0",
    access: [{ type: "s3", url: "s3://example-bucket/tiles/", auth: "none" }],
    notes: HOSTILE_NOTES,
    status: "active",
    review: { state: "seeded", source: "fixture", source_row: 2 },
  };
  const card = {
    id: entry.id,
    kind: "data",
    name: entry.name,
    summary: entry.summary,
    region: "Nowhere",
    license: entry.license,
    status: "active",
    review: "seeded",
  };
  writeFileSync(
    join(dir, "index.json"),
    JSON.stringify({
      format_version: 1,
      generated_at: "2026-01-01T00:00:00Z",
      count: 1,
      entries: [card],
      operations_count: 0,
      operations: [],
    }),
  );
  const db = new DatabaseSync(join(dir, "registry.sqlite"));
  db.exec(`CREATE TABLE entries (id TEXT PRIMARY KEY, kind TEXT, name TEXT, status TEXT, card TEXT, entry TEXT);
    CREATE TABLE operations (id TEXT PRIMARY KEY, name TEXT, status TEXT, card TEXT, entry TEXT);
    CREATE TABLE implementations (id TEXT PRIMARY KEY, implements TEXT, software TEXT, name TEXT, status TEXT, card TEXT, entry TEXT);`);
  db.prepare("INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?)").run(
    entry.id,
    "data",
    entry.name,
    "active",
    JSON.stringify(card),
    JSON.stringify(entry),
  );
  db.close();
}
