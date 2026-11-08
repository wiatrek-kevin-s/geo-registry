// T-1: five fixed entries' pages show every field the design spec's Screens
// table lists for their kind, with the YAML value, or "Not stated" when absent.
// Run after `npm run build` (any base).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parse as parseHtml } from "node-html-parser";
import { parse as parseYaml } from "yaml";

const SITE_DIST = resolve(import.meta.dirname, "../../dist");
const ENTRIES = resolve(import.meta.dirname, "../../../entries");
const FOLDER = { data: "data", tool: "tools", operation: "operations" };
const REVIEW = {
  reviewed: "Reviewed by a person",
  seeded: "Unverified lead from the seed atlas",
  draft: "Draft: written, not yet checked by a person",
  harvested: "Harvested from the engine, not yet checked by a person",
};

const norm = (s) => String(s).replace(/\s+/g, " ").trim();
const scalar = (v) => (v === true ? "yes" : v === false ? "no" : String(v));

function load(kind, id) {
  const yaml = parseYaml(readFileSync(resolve(ENTRIES, FOLDER[kind], `${id}.yaml`), "utf8"));
  const html = readFileSync(resolve(SITE_DIST, FOLDER[kind], id, "index.html"), "utf8");
  return { yaml, root: parseHtml(html), html };
}

function cell(root, field) {
  const row = root.querySelector(`tr[data-field="${field}"] td`);
  assert.ok(row, `row ${field} is on the page`);
  return norm(row.text);
}

/** Field present in YAML: every value appears. Absent: "Not stated". */
function expectField(root, field, value) {
  const text = cell(root, field);
  const blank =
    value === undefined || value === null || (Array.isArray(value) && value.length === 0);
  if (blank) {
    assert.match(text, /Not stated/, `${field} shows Not stated`);
    return;
  }
  const values = Array.isArray(value) ? value : [value];
  for (const v of values) assert.ok(text.includes(norm(scalar(v))), `${field} shows ${v}: ${text}`);
}

function expectHeader(root, yaml) {
  assert.equal(root.querySelectorAll("h1").length, 1, "one h1");
  assert.equal(norm(root.querySelector("h1").text), norm(yaml.name), "name");
  const summary = norm(root.querySelector(".summary").text);
  assert.equal(summary, yaml.summary ? norm(yaml.summary) : "Not stated", "summary");
  const badge = norm(root.querySelector(".badge[data-review]").text);
  assert.ok(badge.startsWith(REVIEW[yaml.review.state]), `badge: ${badge}`);
  if (yaml.review.state === "reviewed" && yaml.review.reviewed_on) {
    assert.ok(badge.includes(String(yaml.review.reviewed_on)), "badge shows reviewed_on");
  }
  const src = root.querySelector("a[data-source-yaml]");
  assert.ok(src, "View source YAML link");
  assert.ok(src.getAttribute("href").endsWith(`/${yaml.id}.yaml`));
}

function expectRetired(root, yaml) {
  const banner = root.querySelector("[data-retired]");
  if (yaml.status === "retired") {
    assert.ok(banner, "retired banner");
    if (yaml.replaced_by) {
      assert.ok(
        banner.querySelector(`a[href$="/data/${yaml.replaced_by}/"]`) ||
          banner.querySelector(`a[href$="/${yaml.replaced_by}/"]`),
        "banner links replaced_by",
      );
    }
  } else {
    assert.equal(banner, null, "no retired banner on an active entry");
  }
}

function checkData(id) {
  const { yaml, root } = load("data", id);
  expectHeader(root, yaml);
  expectRetired(root, yaml);
  for (const f of [
    "publisher",
    "themes",
    "update",
    "formats_out",
    "status",
    "last_verified",
    "notes",
    "related",
  ]) {
    expectField(root, f, yaml[f]);
  }
  expectField(root, "coverage", yaml.coverage?.region);
  if (yaml.coverage?.bbox) {
    assert.ok(cell(root, "coverage").includes(yaml.coverage.bbox.join(", ")), "bbox");
  }
  expectField(root, "license", yaml.license);
  if (yaml.license_original) expectField(root, "license", yaml.license_original);
  expectField(root, "recipe", yaml.recipe?.steps);
  // access endpoints table: one row per endpoint with type, URL, auth, notes
  const rows = root.querySelectorAll('table[data-field="access"] tbody tr');
  assert.equal(rows.length, yaml.access.length, "one access row per endpoint");
  yaml.access.forEach((a, i) => {
    const t = norm(rows[i].text);
    for (const v of [a.type, a.url, a.auth, a.notes ?? "Not stated", a.index ?? "Not stated"]) {
      assert.ok(t.includes(norm(v)), `access ${i} shows ${v}`);
    }
  });
}

function checkTool(id) {
  const { yaml, root } = load("tool", id);
  expectHeader(root, yaml);
  expectRetired(root, yaml);
  for (const f of [
    "category",
    "subcategory",
    "tool_kind",
    "license",
    "open_source",
    "language",
    "interfaces",
    "call",
    "project_status",
    "url",
    "notes",
    "also_categories",
    "related",
  ]) {
    expectField(root, f, yaml[f]);
  }
}

function checkOperation(id) {
  const { yaml, root } = load("operation", id);
  expectHeader(root, yaml);
  expectRetired(root, yaml);
  for (const f of ["aka", "checks", "broader", "narrower", "related"])
    expectField(root, f, yaml[f]);
  const pitfalls = root.querySelectorAll(".callout-pitfall").map((n) => norm(n.text));
  assert.equal(pitfalls.length, (yaml.pitfalls ?? []).length, "one callout per pitfall");
  (yaml.pitfalls ?? []).forEach((p, i) => assert.ok(pitfalls[i].includes(norm(p))));
  const paramRows = root.querySelectorAll('table[data-field="parameters"] tbody tr');
  const params = Object.entries(yaml.parameters ?? {});
  assert.equal(paramRows.length, params.length, "one row per parameter");
  params.forEach(([name, p], i) => {
    const t = norm(paramRows[i].text);
    assert.ok(t.includes(name) && t.includes(p.type), `parameter ${name}`);
    if (p.default !== undefined) assert.ok(t.includes(scalar(p.default)), `${name} default`);
    for (const v of p.values ?? []) assert.ok(t.includes(scalar(v)), `${name} value ${v}`);
  });
  const portText = norm(root.querySelector('table[data-field="inputs"]').text);
  for (const port of [...yaml.inputs, ...yaml.outputs]) {
    assert.ok(portText.includes(port.name) && portText.includes(port.type), `port ${port.name}`);
  }
  const engines = root.querySelectorAll('table[data-field="engines"] tbody tr');
  assert.ok(engines.length > 0, "engine table has rows");
  return engines;
}

test("data: txgio-lidar (reviewed, no recipe)", () => {
  checkData("txgio-lidar");
  const { root } = load("data", "txgio-lidar");
  assert.match(cell(root, "recipe"), /^Not stated$/, "Recipe row reads Not stated");
});

test("data: census-tiger-line (reviewed, with recipe)", () => checkData("census-tiger-line"));

test("data: tiger-line-road-features (retired, replaced by census-tiger-line)", () => {
  checkData("tiger-line-road-features");
});

test("tool: pdal (seeded)", () => checkTool("pdal"));

test("operation: buffer (engine table lists ST_Buffer)", () => {
  const engines = checkOperation("buffer");
  const text = engines.map((r) => norm(r.text)).join(" | ");
  assert.ok(/ST_Buffer/.test(text), "PostGIS ST_Buffer is in the engine table");
});
