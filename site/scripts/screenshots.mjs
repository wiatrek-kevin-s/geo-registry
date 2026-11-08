// T-6 evidence: six screens at 375 and 1,280 px, in light and dark (24 PNGs in evidence/).
// Run after `npm run build`.
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { chromium } from "@playwright/test";

const PORT = 4323;
let base = process.env.SITE_BASE || "/geo-registry/";
if (!base.endsWith("/")) base = `${base}/`;
const SCREENS = [
  ["home", ""],
  ["search-results", "search/?q=lidar"],
  ["search-empty", "search/?q=zzzzqqqq"],
  ["data", "data/txgio-lidar/"],
  ["operation-buffer", "operations/buffer/"],
  ["404", "implementations/gdal/does-not-exist/"],
];

mkdirSync("evidence", { recursive: true });
const server = spawn("node", ["scripts/serve.mjs", String(PORT)], { stdio: "ignore" });
await new Promise((r) => setTimeout(r, 800));
const browser = await chromium.launch();
try {
  for (const colorScheme of ["light", "dark"]) {
    for (const width of [375, 1280]) {
      const context = await browser.newContext({
        colorScheme,
        viewport: { width, height: 900 },
      });
      const page = await context.newPage();
      for (const [name, path] of SCREENS) {
        await page.goto(`http://localhost:${PORT}${base}${path}`);
        await page.waitForLoadState("networkidle");
        await page.screenshot({
          path: `evidence/${name}-${width}-${colorScheme}.png`,
          fullPage: true,
        });
      }
      await context.close();
    }
  }
} finally {
  await browser.close();
  server.kill();
}
console.log("24 screenshots written to evidence/");
