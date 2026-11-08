// Registry text is untrusted. It is rendered as escaped plain text; only
// http:// and https:// URLs become links, every other scheme is shown as code.

export type Segment =
  | { type: "text"; value: string }
  | { type: "link"; value: string }
  | { type: "code"; value: string };

const URL_RE = /\b[a-z][a-z0-9+.-]*:\/\/[^\s<>"']+/gi;
const TRAILING = /[).,;:!?\]}]+$/;

export function segments(text: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(URL_RE)) {
    let url = m[0];
    const trail = url.match(TRAILING)?.[0] ?? "";
    if (trail) url = url.slice(0, -trail.length);
    const start = m.index ?? 0;
    if (start > last) out.push({ type: "text", value: text.slice(last, start) });
    out.push({ type: isWebUrl(url) ? "link" : "code", value: url });
    last = start + url.length;
  }
  if (last < text.length) out.push({ type: "text", value: text.slice(last) });
  return out;
}

export function isWebUrl(url: unknown): url is string {
  return typeof url === "string" && /^https?:\/\/\S+$/i.test(url);
}

export function isBlank(v: unknown): boolean {
  return (
    v === undefined ||
    v === null ||
    (typeof v === "string" && v.trim() === "") ||
    (Array.isArray(v) && v.length === 0)
  );
}

export const REVIEW_TEXT: Record<string, string> = {
  reviewed: "Reviewed by a person",
  seeded: "Unverified lead from the seed atlas",
  draft: "Draft: written, not yet checked by a person",
  harvested: "Harvested from the engine, not yet checked by a person",
};

export function reviewState(review: unknown): string {
  if (typeof review === "string") return review;
  if (review && typeof review === "object" && "state" in review) {
    return String((review as { state: unknown }).state);
  }
  return "unknown";
}

export function formatScalar(v: unknown): string {
  if (v === true) return "yes";
  if (v === false) return "no";
  if (Array.isArray(v)) return v.map(formatScalar).join(", ");
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export const fmtCount = (n: number) => n.toLocaleString("en-US");

/** One crosswalk item, as plain words: how a canonical parameter maps onto an engine. */
export function describeCrosswalk(item: unknown): { param?: string; text: string } {
  if (typeof item === "string") return { param: item, text: "" };
  if (!item || typeof item !== "object") return { text: "Not stated" };
  const o = item as Record<string, unknown>;
  const bits: string[] = [];
  if ("fixed" in o) bits.push(`always ${formatScalar(o.fixed)}`);
  if (o.values && typeof o.values === "object") {
    bits.push(
      Object.entries(o.values as Record<string, unknown>)
        .map(([k, v]) => `${k} = ${formatScalar(v)}`)
        .join("; "),
    );
  }
  if (Array.isArray(o.unsupported) && o.unsupported.length) {
    bits.push(`not supported: ${formatScalar(o.unsupported)}`);
  }
  if (typeof o.note === "string") bits.push(o.note);
  return { param: typeof o.param === "string" ? o.param : undefined, text: bits.join(". ") };
}
