import { json } from "../../../lib/api";
import { loadRegistry } from "../../../lib/registry";

export function GET() {
  const reg = loadRegistry();
  const count = (kind: string) => reg.cards.filter((c) => c.kind === kind).length;
  return json(
    JSON.stringify({
      format: 1,
      generated_at: reg.generatedAt,
      counts: {
        data: count("data"),
        tool: count("tool"),
        operation: reg.operations.length,
        implementation: reg.implementations.length,
      },
      registry_commit: reg.commit,
    }),
  );
}
