// T-6 / REQ-10, REQ-11: the theme, the required states, and no sideways scrolling.
import { test, expect } from "@playwright/test";

const SCREENS = [
  "",
  "search/?q=lidar",
  "search/?q=zzzzqqqq",
  "data/txgio-lidar/",
  "operations/buffer/",
  "implementations/gdal/does-not-exist/",
];

test("the site follows a dark device; the toggle switches to light and survives a reload", async ({
  page,
}) => {
  const bg = () => page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor);
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("about/");
  expect(await bg()).toBe("rgb(17, 20, 24)");
  await expect(page.locator("[data-theme-toggle]")).toHaveAttribute(
    "aria-label",
    "Switch to light theme",
  );
  await page.locator("[data-theme-toggle]").click();
  expect(await bg()).toBe("rgb(255, 255, 255)");
  await page.reload();
  expect(await bg()).toBe("rgb(255, 255, 255)");
  await page.goto("contribute/");
  expect(await bg()).toBe("rgb(255, 255, 255)");
});

test("search shows Searching… while Pagefind loads", async ({ page }) => {
  await page.route("**/pagefind/pagefind.js", async (route) => {
    await new Promise((r) => setTimeout(r, 800));
    await route.continue();
  });
  await page.goto("search/?q=lidar");
  await expect(page.locator("#search-status")).toHaveText("Searching…");
  await expect(page.locator("#search-form button[type=submit]")).toHaveAttribute(
    "aria-busy",
    "true",
  );
  await expect(page.locator("body[data-search-state=done]")).toBeAttached();
  await expect(page.locator("#search-form button[type=submit]")).toHaveAttribute(
    "aria-busy",
    "false",
  );
});

test("when search fails to load, the controls show it and the lists are linked", async ({
  page,
}) => {
  await page.route("**/pagefind/**", (route) => route.abort());
  await page.goto("search/?q=lidar");
  await expect(page.locator("#search-error")).toBeVisible();
  await expect(page.locator("#q")).toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#search-form button[type=submit]")).toBeDisabled();
});

test("focus shows a visible ring", async ({ page }) => {
  await page.goto("about/");
  await page.keyboard.press("Tab");
  const link = page.locator(".skip-link");
  await expect(link).toBeFocused();
  expect(await link.evaluate((e) => getComputedStyle(e).outlineStyle)).toBe("solid");
  expect(await link.evaluate((e) => getComputedStyle(e).outlineWidth)).toBe("2px");
});

test("the sidebar is a Sections button on a phone and a list on a laptop", async ({ page }) => {
  await page.goto("data/");
  const button = page.locator(".sidebar-toggle");
  const list = page.locator("#sidebar-body");
  const width = page.viewportSize()?.width ?? 0;
  if (width < 768) {
    await expect(button).toBeVisible();
    await expect(list).toBeHidden();
    await button.click();
    await expect(button).toHaveAttribute("aria-expanded", "true");
    await expect(list).toBeVisible();
  } else {
    await expect(button).toBeHidden();
    await expect(list).toBeVisible();
  }
});

for (const path of SCREENS) {
  test(`nothing overflows sideways: /${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator("#content")).toBeVisible();
    await page.waitForLoadState("networkidle");
    const { scroll, client } = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      client: document.documentElement.clientWidth,
    }));
    expect(scroll).toBeLessThanOrEqual(client);
  });
}
