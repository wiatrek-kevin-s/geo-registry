// T-2 / REQ-4: each Lookups query reaches its target within 3 interactions
// from the home page: type the query (1), press Enter (2), click the result (3).
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

interface Lookup {
  query: string;
  targets: { kind: "data" | "tool" | "operation"; id: string }[];
}
const FOLDER = { data: "data", tool: "tools", operation: "operations" };
const lookups: Lookup[] = JSON.parse(
  readFileSync(resolve(import.meta.dirname, "../lookups.json"), "utf8"),
).lookups;

for (const l of lookups) {
  test(`lookup: ${l.query}`, async ({ page }) => {
    await page.goto("./");
    const box = page.getByLabel("Search data sources, tools and operations");
    await box.fill(l.query); // interaction 1
    await box.press("Enter"); // interaction 2
    await expect(page.locator("body[data-search-state=done]")).toBeAttached();
    const selector = l.targets.map((t) => `.result[data-id="${t.id}"] a`).join(", ");
    const link = page.locator(selector).first();
    await expect(link).toBeVisible();
    await link.click(); // interaction 3
    const paths = l.targets.map((t) => `/${FOLDER[t.kind]}/${t.id}/`);
    expect(paths.some((p) => new URL(page.url()).pathname.endsWith(p))).toBe(true);
    await expect(page.locator("h1")).toBeVisible();
  });
}
