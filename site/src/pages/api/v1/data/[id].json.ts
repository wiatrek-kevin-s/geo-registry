import type { APIContext } from "astro";
import { cardEntry } from "../../../../lib/api";
import { loadRegistry } from "../../../../lib/registry";

export function getStaticPaths() {
  return loadRegistry()
    .cards.filter((c) => c.kind === "data")
    .map((c) => ({ params: { id: c.id } }));
}

export const GET = ({ params }: APIContext) => cardEntry("data", params.id as string);
