import type { APIContext } from "astro";
import { cardEntry } from "../../../../lib/api";
import { loadRegistry } from "../../../../lib/registry";

export function getStaticPaths() {
  return loadRegistry().operations.map((c) => ({ params: { id: c.id } }));
}

export const GET = ({ params }: APIContext) => cardEntry("operation", params.id as string);
