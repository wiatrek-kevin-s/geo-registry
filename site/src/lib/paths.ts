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

export function implPath(software: string, id: string): string {
  return href(`implementations/${software}/${id}/`);
}

export function enginePath(software: string): string {
  return href(`engines/${software}/`);
}

/** Variants exist only as a mapping file; every other implementation is harvested. */
export function implSource(software: string, id: string, isVariant: boolean): string {
  const folder = isVariant ? "mappings" : "implementations";
  return `${REPO}/blob/main/${folder}/${software}/${id}.yaml`;
}

/** Absolute URL of a site path, on whatever origin and base this build targets. */
export function absolute(path: string): string {
  return new URL(href(path), import.meta.env.SITE).href;
}
