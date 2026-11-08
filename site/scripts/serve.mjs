// Minimal static server for tests: serves dist/ under SITE_BASE, like GitHub Pages.
// Usage: node scripts/serve.mjs [port] [distDir]
import { createServer } from "node:http";
import { existsSync, readFileSync, statSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";

const port = Number(process.argv[2] || 4322);
const dist = resolve(process.argv[3] || "dist");
let base = process.env.SITE_BASE || "/geo-registry/";
if (!base.startsWith("/")) base = `/${base}`;
if (!base.endsWith("/")) base = `${base}/`;
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".woff2": "font/woff2",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".pf_meta": "application/octet-stream",
};

createServer((req, res) => {
  const path = decodeURIComponent(new URL(req.url, "http://x").pathname);
  let file = null;
  if (path.startsWith(base)) {
    const rel = normalize(path.slice(base.length)).replace(/^(\.\.[/\\])+/, "");
    let f = join(dist, rel);
    if (existsSync(f) && statSync(f).isDirectory()) f = join(f, "index.html");
    if (existsSync(f) && f.startsWith(dist)) file = f;
  }
  if (!file) {
    const notFound = join(dist, "404.html");
    res.writeHead(404, { "content-type": TYPES[".html"] });
    res.end(existsSync(notFound) ? readFileSync(notFound) : "Not found");
    return;
  }
  res.writeHead(200, { "content-type": TYPES[extname(file)] || "application/octet-stream" });
  res.end(readFileSync(file));
}).listen(port, () => console.log(`Serving ${dist} at http://localhost:${port}${base}`));
