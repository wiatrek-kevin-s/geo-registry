// The static JSON API (format F-2). The `entry` value is spliced in from the
// stored text, so it stays exactly as registry.sqlite holds it.
import { absolute, FOLDER, implSource, sourceUrl } from "./paths";
import { loadRegistry, type Kind } from "./registry";

const JSON_TYPE = { "Content-Type": "application/json" };

export function json(body: string | Uint8Array): Response {
  return new Response(body as BodyInit, { headers: JSON_TYPE });
}

function envelope(kind: Kind, id: string, url: string, source: string): Response {
  const reg = loadRegistry();
  const raw = reg.raw.get(`${kind}/${id}`);
  if (raw === undefined) throw new Error(`No stored entry for ${kind}/${id}`);
  const head = { format: 1, id, kind, registry_commit: reg.commit, url, source };
  return json(`${JSON.stringify(head).slice(0, -1)},"entry":${raw}}`);
}

export function cardEntry(kind: Exclude<Kind, "implementation">, id: string): Response {
  return envelope(kind, id, absolute(`${FOLDER[kind]}/${id}/`), sourceUrl(kind, id));
}

export function implementationEntry(software: string, id: string, isVariant: boolean): Response {
  return envelope(
    "implementation",
    id,
    absolute(`implementations/${software}/${id}/`),
    implSource(software, id, isVariant),
  );
}
