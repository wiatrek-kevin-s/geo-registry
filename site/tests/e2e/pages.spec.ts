// T-5 / REQ-2, REQ-9: the 404 page and implementation search ranking.
import { test, expect } from "@playwright/test";

test("a missing implementation shows a search for its id and links the operations", async ({
  page,
}) => {
  const res = await page.goto("implementations/gdal/does-not-exist/");
  expect(res?.status()).toBe(404);
  await expect(page.locator("h1")).toHaveText("Page not found");
  await expect(page.locator("#missing-q")).toHaveValue("does-not-exist");
  await expect(page.locator("#implementation-note")).toBeVisible();
  await expect(page.locator('[data-browse-links] a[href$="/operations/"]')).toBeVisible();
  await page.locator("#missing-q").press("Enter");
  await expect(page).toHaveURL(/search\/\?q=does-not-exist/);
});

test("searching buffer shows the Buffer operation first, above every implementation", async ({
  page,
}) => {
  await page.goto("search/?q=buffer");
  await expect(page.locator("body[data-search-state=done]")).toBeAttached();
  const results = await page
    .locator(".result")
    .evaluateAll((els) => els.map((e) => (e as HTMLElement).dataset));
  expect(results[0]).toMatchObject({ kind: "operation", id: "buffer" });
  const firstImpl = results.findIndex((r) => r.kind === "implementation");
  expect(firstImpl).toBeGreaterThan(0);
});

test("an operation's engine table links its implementations", async ({ page }) => {
  await page.goto("operations/buffer/");
  const link = page.locator('tr[data-implementation="postgis-st-buffer"] td a').nth(1);
  await expect(link).toHaveText("st_buffer");
  await link.click();
  await expect(page).toHaveURL(/implementations\/postgis\/postgis-st-buffer\/$/);
  await expect(page.locator("h1")).toHaveText("st_buffer");
  await expect(page.locator("[data-field=signatures]")).toContainText("geography");
  await expect(page.locator(".entry-meta .badge")).toHaveText(
    "Draft: written, not yet checked by a person",
  );
});
