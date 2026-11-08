import type { APIContext } from "astro";
import { implementationEntry } from "../../../../../lib/api";
import { loadRegistry } from "../../../../../lib/registry";

export function getStaticPaths() {
  return loadRegistry().implementations.map((i) => ({
    params: { software: i.software, id: i.id },
    props: { isVariant: Boolean(i.entry.variant_of) },
  }));
}

export const GET = ({ params, props }: APIContext) =>
  implementationEntry(params.software as string, params.id as string, props.isVariant as boolean);
