// URL helpers. Every internal link goes through Astro's base (SITE_BASE).
import type { Kind } from "./registry";

export const REPO = "https://github.com/wiatrek-kevin-s/geo-registry";

export const FOLDER: Record<Exclude<Kind, "implementation">, string> = {
  data: "data",
  tool: "tools",
  operation: "operations",
};

/** Join a site path (no leading slash needed) onto the configured base. */
export function href(path = ""): string {
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`;
  return base + path.replace(/^\/+/, "");
}

export function entryPath(kind: Exclude<Kind, "implementation">, id: string): string {
  return href(`${FOLDER[kind]}/${id}/`);
}

export function sourceUrl(kind: Exclude<Kind, "implementation">, id: string): string {
  return `${REPO}/blob/main/entries/${FOLDER[kind]}/${id}.yaml`;
}
