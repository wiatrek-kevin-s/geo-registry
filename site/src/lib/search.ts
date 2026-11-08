// Search weights and labels (build brief, "Search").
export const KIND_LABEL = {
  data: "Data source",
  tool: "Tool",
  operation: "Operation",
  implementation: "Implementation",
} as const;

export const LIST_LABEL = { data: "Data", tool: "Tools", operation: "Operations" } as const;

/** Retired entries carry weight 0.3, so every weight on their page is scaled by it. */
export const RETIRED_FACTOR = 0.3;
/** Implementation pages carry weight 0.5, so "buffer" finds the operation before its engines. */
export const IMPLEMENTATION_FACTOR = 0.5;

export function searchWeight(weight: number, retired: boolean, factor = 1): string {
  return String(Math.round((retired ? weight * RETIRED_FACTOR : weight) * factor * 100) / 100);
}
