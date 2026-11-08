// Reads the registry build output (dist/index.json and dist/registry.sqlite).
// The site never reads entries/ directly, so it matches what Columbus servers download.
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { DatabaseSync } from "node:sqlite";

export type Kind = "data" | "tool" | "operation" | "implementation";

/* eslint-disable @typescript-eslint/no-explicit-any -- registry entries are open-ended JSON */
export type Entry = Record<string, any>;

export interface Card {
  id: string;
  kind: Kind;
  name: string;
  summary?: string;
  status: string;
  review?: string;
  [key: string]: unknown;
}

export interface Implementation {
  id: string;
  software: string;
  implements: string | null;
  name: string;
  status: string;
  card: Card;
  entry: Entry;
}

export interface Registry {
  generatedAt: string;
  commit: string;
  cards: Card[];
  operations: Card[];
  entries: Map<string, Entry>; // key: `${kind}/${id}`
  implementations: Implementation[];
  ids: { data: Set<string>; tool: Set<string>; operation: Set<string> };
}

const DIST_DIR = resolve(process.env.REGISTRY_DIST || resolve(process.cwd(), "../dist"));

function registryCommit(): string {
  if (process.env.REGISTRY_COMMIT) return process.env.REGISTRY_COMMIT;
  if (process.env.GITHUB_SHA) return process.env.GITHUB_SHA;
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8", stdio: "pipe" }).trim();
  } catch {
    // Local fallback without git: follow .git/HEAD to a loose ref.
    try {
      const gitDir = resolve(DIST_DIR, "../.git");
      const head = readFileSync(resolve(gitDir, "HEAD"), "utf8").trim();
      if (/^[0-9a-f]{40}$/.test(head)) return head;
      const ref = head.replace(/^ref: /, "");
      return readFileSync(resolve(gitDir, ref), "utf8").trim();
    } catch {
      return "unknown";
    }
  }
}

let cached: Registry | undefined;

export function loadRegistry(): Registry {
  if (cached) return cached;
  const indexPath = resolve(DIST_DIR, "index.json");
  const dbPath = resolve(DIST_DIR, "registry.sqlite");
  if (!existsSync(indexPath) || !existsSync(dbPath)) {
    throw new Error("dist/ not found: run the registry build first");
  }
  const index = JSON.parse(readFileSync(indexPath, "utf8"));
  const db = new DatabaseSync(dbPath, { readOnly: true });
  const entries = new Map<string, Entry>();
  for (const row of db.prepare("SELECT kind, id, entry FROM entries").all() as {
    kind: string;
    id: string;
    entry: string;
  }[]) {
    entries.set(`${row.kind}/${row.id}`, JSON.parse(row.entry));
  }
  for (const row of db.prepare("SELECT id, entry FROM operations").all() as {
    id: string;
    entry: string;
  }[]) {
    entries.set(`operation/${row.id}`, JSON.parse(row.entry));
  }
  const implementations: Implementation[] = (
    db
      .prepare(
        "SELECT id, software, implements, name, status, card, entry FROM implementations ORDER BY software, id",
      )
      .all() as Record<string, string | null>[]
  ).map((r) => ({
    id: r.id as string,
    software: r.software as string,
    implements: r.implements,
    name: r.name as string,
    status: r.status as string,
    card: JSON.parse(r.card as string),
    entry: JSON.parse(r.entry as string),
  }));
  db.close();

  const cards: Card[] = index.entries;
  const operations: Card[] = index.operations;
  for (const c of [...cards, ...operations]) {
    if (!entries.has(`${c.kind}/${c.id}`)) {
      throw new Error(`registry.sqlite has no full entry for ${c.kind} ${c.id}`);
    }
  }
  cached = {
    generatedAt: index.generated_at,
    commit: registryCommit(),
    cards,
    operations,
    entries,
    implementations,
    ids: {
      data: new Set(cards.filter((c) => c.kind === "data").map((c) => c.id)),
      tool: new Set(cards.filter((c) => c.kind === "tool").map((c) => c.id)),
      operation: new Set(operations.map((c) => c.id)),
    },
  };
  return cached;
}

export function getEntry(kind: Kind, id: string): Entry {
  const e = loadRegistry().entries.get(`${kind}/${id}`);
  if (!e) throw new Error(`No entry ${kind}/${id}`);
  return e;
}

export const byName = (a: { name: string }, b: { name: string }) =>
  a.name.localeCompare(b.name, "en", { sensitivity: "base" });
