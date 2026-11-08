// T-5 / REQ-8: the static JSON API (format F-2) matches the registry build.
// Run after `npm run build` (any base).
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";

const API = resolve(import.meta.dirname, "../../dist/api/v1");
const SITE = resolve(import.meta.dirname, "../../dist");
const DIST = resolve(import.meta.dirname, "../../../dist");
const db = new DatabaseSync(resolve(DIST, "registry.sqlite"), { readOnly: true });
const n = (sql) => db.prepare(sql).get().n;
const counts = {
  data: n("SELECT count(*) n FROM entries WHERE kind='data'"),
  tool: n("SELECT count(*) n FROM entries WHERE kind='tool'"),
  operation: n("SELECT count(*) n FROM operations"),
  implementation: n("SELECT count(*) n FROM implementations"),
};
const meta = JSON.parse(readFileSync(resolve(API, "meta.json"), "utf8"));

// Every 150th row, so the sample is fixed and spans each kind.
const pick = (sql) =>
  db
    .prepare(sql)
    .all()
    .filter((_, i) => i % 150 === 0);
const samples = [
  ...pick("SELECT id, entry FROM entries WHERE kind='data' ORDER BY id").map((r) => ({
    ...r,
    kind: "data",
    file: `data/${r.id}.json`,
    source: `entries/data/${r.id}.yaml`,
    path: `data/${r.id}/`,
  })),
  ...pick("SELECT id, entry FROM entries WHERE kind='tool' ORDER BY id").map((r) => ({
    ...r,
    kind: "tool",
    file: `tools/${r.id}.json`,
    source: `entries/tools/${r.id}.yaml`,
    path: `tools/${r.id}/`,
  })),
  ...pick("SELECT id, entry FROM operations ORDER BY id").map((r) => ({
    ...r,
    kind: "operation",
    file: `operations/${r.id}.json`,
    source: `entries/operations/${r.id}.yaml`,
    path: `operations/${r.id}/`,
  })),
  ...pick("SELECT id, software, entry FROM implementations ORDER BY id").map((r) => ({
    ...r,
    kind: "implementation",
    file: `implementations/${r.software}/${r.id}.json`,
    source: `${r.entry.includes('"variant_of"') ? "mappings" : "implementations"}/${r.software}/${r.id}.yaml`,
    path: `implementations/${r.software}/${r.id}/`,
  })),
];

test("meta.json carries the format, date, commit and the counts in dist", () => {
  assert.deepEqual(meta.counts, counts);
  assert.equal(meta.format, 1);
  const index = JSON.parse(readFileSync(resolve(DIST, "index.json"), "utf8"));
  assert.equal(meta.generated_at, index.generated_at);
  assert.match(meta.registry_commit, /^[0-9a-f]{40}$/);
});

test("index.json is a byte-for-byte copy", () => {
  assert.ok(
    readFileSync(resolve(API, "index.json")).equals(readFileSync(resolve(DIST, "index.json"))),
  );
});

test("there is one API file per entry", () => {
  for (const [folder, count] of [
    ["data", counts.data],
    ["tools", counts.tool],
    ["operations", counts.operation],
  ]) {
    assert.equal(readdirSync(resolve(API, folder)).length, count, folder);
  }
  const impl = readdirSync(resolve(API, "implementations"), { recursive: true }).filter((f) =>
    f.endsWith(".json"),
  );
  assert.equal(impl.length, counts.implementation);
});

test("sampled per-entry files match the F-2 shape", () => {
  assert.ok(samples.length >= 10, `sampled ${samples.length}`);
  for (const s of samples) {
    const text = readFileSync(resolve(API, s.file), "utf8");
    assert.notEqual(text.charCodeAt(0), 0xfeff, "no BOM");
    assert.ok(text.endsWith(`,"entry":${s.entry}}`), `${s.file}: entry exactly as stored`);
    const doc = JSON.parse(text);
    assert.deepEqual(Object.keys(doc), [
      "format",
      "id",
      "kind",
      "registry_commit",
      "url",
      "source",
      "entry",
    ]);
    assert.equal(doc.format, 1);
    assert.equal(doc.id, s.id);
    assert.equal(doc.kind, s.kind, "singular kind");
    assert.equal(doc.registry_commit, meta.registry_commit);
    assert.match(doc.url, new RegExp(`^https://.+/${s.path}$`));
    assert.equal(
      doc.source,
      `https://github.com/wiatrek-kevin-s/geo-registry/blob/main/${s.source}`,
    );
  }
});

test("every source path points at a YAML file in the repo", () => {
  const rows = db.prepare("SELECT id, software, entry FROM implementations").all();
  const root = resolve(DIST, "..");
  for (const r of rows) {
    const folder = r.entry.includes('"variant_of"') ? "mappings" : "implementations";
    assert.ok(existsSync(resolve(root, folder, r.software, `${r.id}.yaml`)), r.id);
  }
});

test("every implementation has a page", () => {
  const pages = readdirSync(resolve(SITE, "implementations"), { recursive: true }).filter((f) =>
    f.endsWith("index.html"),
  );
  assert.equal(pages.length, counts.implementation);
});
