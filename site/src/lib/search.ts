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
export function searchWeight(weight: number, retired: boolean): string {
  return String(Math.round((retired ? weight * RETIRED_FACTOR : weight) * 100) / 100);
}
