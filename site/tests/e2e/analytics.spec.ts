// T-9: the Cloudflare beacon is the only third-party request, and only with a token.
import { test, expect } from "@playwright/test";

const TOKEN = process.env.CF_BEACON_TOKEN;

test("third-party requests are the analytics script and nothing else", async ({
  page,
  baseURL,
}) => {
  const origin = new URL(baseURL as string).origin;
  const external: string[] = [];
  page.on("request", (r) => {
    if (new URL(r.url()).origin !== origin && !r.url().startsWith("data:")) external.push(r.url());
  });
  await page.goto("");
  await page.waitForLoadState("networkidle");
  const beacons = page.locator("script[data-cf-beacon]");
  if (TOKEN) {
    expect(external).toEqual(["https://static.cloudflareinsights.com/beacon.min.js"]);
    await expect(beacons).toHaveCount(1);
    expect(JSON.parse((await beacons.getAttribute("data-cf-beacon")) as string)).toEqual({
      token: TOKEN,
    });
  } else {
    expect(external).toEqual([]);
    await expect(beacons).toHaveCount(0);
  }
});
