// Checks every internal link, script, stylesheet and font in the built site.
// Usage: node scripts/check-links.mjs [distDir]   (reads SITE_URL and SITE_BASE like the build)
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { parse } from "node-html-parser";

const distDir = resolve(process.argv[2] || "dist");
const site = (process.env.SITE_URL || "https://wiatrek-kevin-s.github.io").replace(/\/+$/, "");
let base = process.env.SITE_BASE || "/geo-registry/";
if (!base.startsWith("/")) base = `/${base}`;
if (!base.endsWith("/")) base = `${base}/`;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

/** Map a URL found in `fromFile` to a file in dist, or return null when it is external. */
function target(url, fromFile) {
  if (!url || url.startsWith("#") || /^(mailto|tel|data|javascript):/i.test(url)) return null;
  let path;
  if (/^https?:\/\//i.test(url)) {
    if (!url.startsWith(site + "/")) return null; // external
    path = url.slice(site.length);
  } else if (url.startsWith("//")) {
    return null;
  } else if (url.startsWith("/")) {
    path = url;
  } else {
    // relative: resolve against the referring file's URL path
    const rel = fromFile.slice(distDir.length).split("\\").join("/");
    const dirUrl = base + rel.replace(/^\//, "").replace(/[^/]*$/, "");
    path = new URL(url, `https://x${dirUrl}`).pathname;
  }
  path = decodeURI(path.split(/[?#]/)[0]);
  if (!path.startsWith(base)) return { path, file: null };
  let file = join(distDir, path.slice(base.length));
  if (path.endsWith("/")) file = join(file, "index.html");
  return { path, file };
}

const broken = [];
let checked = 0;
let pages = 0;
for (const file of walk(distDir)) {
  const urls = [];
  if (file.endsWith(".html")) {
    pages++;
    const root = parse(readFileSync(file, "utf8"));
    for (const el of root.querySelectorAll("a[href], link[href]"))
      urls.push(el.getAttribute("href"));
    for (const el of root.querySelectorAll("script[src], img[src], source[src]")) {
      urls.push(el.getAttribute("src"));
    }
  } else if (file.endsWith(".css")) {
    for (const m of readFileSync(file, "utf8").matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)) {
      urls.push(m[1]);
    }
  } else continue;
  for (const url of urls) {
    const t = target(url, file);
    if (!t) continue;
    checked++;
    if (!t.file || !existsSync(t.file)) {
      broken.push(`${file.slice(distDir.length)} -> ${url}`);
    }
  }
}

console.log(`Checked ${checked} internal links in ${pages} pages (base ${base}).`);
if (broken.length) {
  console.error(`${broken.length} broken internal links:`);
  for (const b of broken.slice(0, 50)) console.error(`  ${b}`);
  process.exit(1);
}
console.log("0 broken internal links.");
