// @ts-check
import { defineConfig } from "astro/config";

// SITE_URL and SITE_BASE come from the build environment (repo variables in CI).
// Defaults match the github.io address used until the custom domain is live.
const site = process.env.SITE_URL || "https://wiatrek-kevin-s.github.io";
let base = process.env.SITE_BASE || "/geo-registry/";
if (!base.startsWith("/")) base = `/${base}`;
if (!base.endsWith("/")) base = `${base}/`;

export default defineConfig({
  site,
  base,
  trailingSlash: "always",
  build: { format: "directory" },
  compressHTML: true,
  devToolbar: { enabled: false },
});
