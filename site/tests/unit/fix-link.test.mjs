// T-7 / REQ-13: "Suggest a fix" opens the F-5 form, prefilled. Run after `npm run build`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parse as parseHtml } from "node-html-parser";
import { parse as parseYaml } from "yaml";

const DIST = resolve(import.meta.dirname, "../../dist");
const TEMPLATE = resolve(import.meta.dirname, "../../../.github/ISSUE_TEMPLATE/fix-entry.yml");

function link(page) {
  const root = parseHtml(readFileSync(resolve(DIST, page, "index.html"), "utf8"));
  const a = root.querySelector("a[data-suggest-fix]");
  assert.ok(a, `${page} has a Suggest a fix link`);
  assert.equal(a.text.trim(), "Suggest a fix");
  return new URL(a.getAttribute("href"));
}

const CASES = [
  ["data", "txgio-lidar", "data/txgio-lidar"],
  ["tool", "pdal", "tools/pdal"],
  ["operation", "buffer", "operations/buffer"],
  ["implementation", "postgis-st-buffer", "implementations/postgis/postgis-st-buffer"],
];

for (const [kind, id, page] of CASES) {
  test(`suggest a fix on ${kind} ${id} is prefilled`, () => {
    const url = link(page);
    assert.equal(
      url.origin + url.pathname,
      "https://github.com/wiatrek-kevin-s/geo-registry/issues/new",
    );
    assert.equal(url.searchParams.get("template"), "fix-entry.yml");
    assert.equal(url.searchParams.get("title"), `Fix: ${kind} ${id}`);
    assert.equal(url.searchParams.get("entry_id"), id);
    assert.match(url.searchParams.get("page_url"), new RegExp(`^https://.+/${page}/$`));
    assert.ok(!url.search.includes("+"), "spaces are %20");
  });
}

test("the issue form has the F-5 fields and label", () => {
  const form = parseYaml(readFileSync(TEMPLATE, "utf8"));
  assert.deepEqual(form.labels, ["fix-request"]);
  const fields = form.body.map((b) => [b.id, b.type, b.validations.required]);
  assert.deepEqual(fields, [
    ["entry_id", "input", true],
    ["page_url", "input", true],
    ["what_is_wrong", "textarea", true],
    ["should_say", "textarea", true],
    ["evidence", "textarea", false],
  ]);
});
