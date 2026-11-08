// T-6 / REQ-10: 0 serious or critical axe violations, in light and dark.
import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const { pages } = JSON.parse(
  readFileSync(new URL("../a11y-pages.json", import.meta.url), "utf8"),
) as { pages: string[] };

for (const colorScheme of ["light", "dark"] as const) {
  for (const path of pages) {
    test(`axe ${colorScheme}: /${path}`, async ({ page }) => {
      test.setTimeout(120_000);
      await page.emulateMedia({ colorScheme });
      await page.goto(path);
      if (path.startsWith("search/")) {
        await expect(page.locator("body[data-search-state=done]")).toBeAttached();
      }
      const { violations } = await new AxeBuilder({ page }).analyze();
      const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(
        bad.map((v) => `${v.id} (${v.nodes.length}): ${v.nodes[0]?.target}`),
        "serious or critical violations",
      ).toEqual([]);
    });
  }
}
