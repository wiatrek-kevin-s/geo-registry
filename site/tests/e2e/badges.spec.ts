// T-2 / REQ-5, REQ-6: review badges, the retired banner, and retired entries
// ranking below active ones; REQ-4's failure case when Pagefind can't load.
import { test, expect } from "@playwright/test";

test("reviewed entry shows the reviewed badge with its date", async ({ page }) => {
  await page.goto("data/txgio-lidar/");
  const badge = page.locator(".entry-meta .badge");
  await expect(badge).toHaveText("Reviewed by a person, 2026-11-05");
});

test("seeded entry shows the unverified badge", async ({ page }) => {
  await page.goto("data/3dbag/");
  await expect(page.locator(".entry-meta .badge")).toHaveText(
    "Unverified lead from the seed atlas",
  );
});

test("retired entry shows the banner linking its replacement", async ({ page }) => {
  await page.goto("data/tiger-line-road-features/");
  const banner = page.locator("[data-retired]");
  await expect(banner).toContainText("Retired");
  await expect(banner.locator('a[href$="/data/census-tiger-line/"]')).toBeVisible();
});

test("every search result shows a review badge", async ({ page }) => {
  await page.goto("search/?q=lidar");
  await expect(page.locator("body[data-search-state=done]")).toBeAttached();
  const results = page.locator(".result");
  expect(await results.count()).toBeGreaterThan(5);
  for (const r of await results.all()) {
    await expect(r.locator(".badge[data-review]")).toHaveText(/\S/);
  }
});

test("a retired entry ranks below the active entry that replaces it", async ({ page }) => {
  await page.goto("search/?q=TIGER%2FLine&kind=Data+source");
  await expect(page.locator("body[data-search-state=done]")).toBeAttached();
  const ids = await page
    .locator(".result")
    .evaluateAll((els) => els.map((e) => (e as HTMLElement).dataset.id));
  const active = ids.indexOf("census-tiger-line");
  const retired = ids.indexOf("tiger-line-road-features");
  expect(active).toBeGreaterThanOrEqual(0);
  expect(retired).toBeGreaterThan(active);
  await expect(
    page.locator('.result[data-id="tiger-line-road-features"] .badge-retired'),
  ).toBeVisible();
});

test("search says so and links the browse lists when Pagefind fails to load", async ({ page }) => {
  await page.route("**/pagefind/**", (route) => route.abort());
  await page.goto("search/?q=lidar");
  const error = page.locator("#search-error");
  await expect(error).toBeVisible();
  await expect(error).toContainText("Search couldn't load");
  for (const path of ["data/", "tools/", "operations/"]) {
    await expect(error.locator(`a[href$="/${path}"]`)).toBeVisible();
  }
});

test("a filter with no matches says so and offers to clear filters", async ({ page }) => {
  await page.goto("search/?q=lidar&kind=Operation");
  await expect(page.locator("body[data-search-state=empty]")).toBeAttached();
  await expect(page.locator("#search-status")).toContainText("No entries match these filters");
  await page.getByRole("link", { name: "Clear filters" }).click();
  await expect(page.locator("body[data-search-state=done]")).toBeAttached();
});
