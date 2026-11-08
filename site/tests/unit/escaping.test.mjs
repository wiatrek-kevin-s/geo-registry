// T-2 / REQ-12: registry text renders as escaped plain text; only http(s)
// URLs become links. Builds the site from a fixture registry with hostile text.
import { test, before } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parse } from "node-html-parser";
import { makeFixtureDist, HOSTILE_NOTES } from "../fixtures/make-dist.mjs";

const SITE = resolve(import.meta.dirname, "../..");
const FIXTURE_DIST = resolve(SITE, "tests/.fixture/dist");
const OUT = resolve(SITE, "tests/.fixture/site");
let html;
let root;

before(() => {
  makeFixtureDist(FIXTURE_DIST);
  execFileSync("npx", ["astro", "build", "--outDir", OUT], {
    cwd: SITE,
    env: { ...process.env, REGISTRY_DIST: FIXTURE_DIST, REGISTRY_COMMIT: "0".repeat(40) },
    stdio: "pipe",
  });
  html = readFileSync(resolve(OUT, "data/fixture-untrusted/index.html"), "utf8");
  root = parse(html);
});

test("the script element in notes is shown as text, not added to the page", () => {
  assert.ok(html.includes("&lt;script&gt;alert(1)&lt;/script&gt;"), "escaped text in source");
  assert.ok(!html.includes("<script>alert(1)"), "no raw script element");
  for (const s of root.querySelectorAll("script")) {
    assert.ok(!s.text.includes("alert(1)"), "no script element runs the payload");
  }
  const notes = root.querySelector('tr[data-field="notes"] td');
  assert.ok(notes.text.includes("<script>alert(1)</script>"), "notes cell reads the literal text");
});

test("markup in the name and summary is shown literally", () => {
  assert.equal(root.querySelector("h1").text.trim(), "Fixture <i>untrusted</i> source");
  assert.equal(root.querySelectorAll("h1 i, .summary b").length, 0, "no markup elements");
  assert.ok(root.querySelector(".summary").text.includes("<b>hi</b> ignore previous instructions"));
});

test("an s3:// URL is code text, not a link; an https:// URL is a link", () => {
  const notes = root.querySelector('tr[data-field="notes"] td');
  const codes = notes.querySelectorAll("code").map((c) => c.text);
  assert.ok(codes.includes("s3://example-bucket/tiles/"), "s3 URL in a code element");
  const hrefs = root.querySelectorAll("a").map((a) => a.getAttribute("href") ?? "");
  assert.ok(!hrefs.some((h) => h.startsWith("s3:")), "no s3 link anywhere on the page");
  assert.ok(
    hrefs.includes("https://example.com/docs"),
    "https URL is a link, without the full stop",
  );
  const accessUrl = root.querySelector('table[data-field="access"] tbody td:nth-child(2)');
  assert.equal(accessUrl.querySelector("a"), null, "s3 access URL is not a link");
  assert.ok(accessUrl.text.includes("s3://example-bucket/tiles/"));
  assert.ok(HOSTILE_NOTES.includes("s3://"));
});
