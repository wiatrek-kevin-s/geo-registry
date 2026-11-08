// County lookup for search (change request CR-1): when a query names a US
// county and no state, also search with the county's state, because statewide
// sources say "Texas", not every county in it.

export interface Gazetteer {
  states: string[];
  counties: Record<string, string[]>;
}

/** Only fetch the county list for queries that could name a county. */
export const MIGHT_NAME_COUNTY = /\b(county|parish|borough|census area|municipio|city)\b/i;

/** At most this many states per county name; "Washington County" is in 30. */
const MAX_STATES = 3;

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const word = (s: string) => new RegExp(`(^|[^a-z0-9])${escape(s)}(?=$|[^a-z0-9])`, "i");

/** Alternative queries with the county replaced by its state; [] when none apply. */
export function expandCounty(query: string, gaz: Gazetteer): string[] {
  const q = query.trim();
  if (!q || !MIGHT_NAME_COUNTY.test(q)) return [];
  if (gaz.states.some((s) => word(s).test(q))) return [];
  let best = "";
  for (const name of Object.keys(gaz.counties)) {
    if (name.length > best.length && word(name).test(q)) best = name;
  }
  if (!best) return [];
  const states = gaz.counties[best] ?? [];
  if (states.length === 0 || states.length > MAX_STATES) return [];
  return states.map((state) =>
    q
      .replace(word(best), (_m, pre: string) => `${pre}${state}`)
      .replace(/\s+/g, " ")
      .trim(),
  );
}
