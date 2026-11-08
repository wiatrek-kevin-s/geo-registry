// Groups for the browse lists and the left sidebar (design spec, "Browse lists").
import { byName, loadRegistry, type Card, type Implementation } from "./registry";
import { enginePath, href } from "./paths";

export interface Group<T> {
  label: string;
  anchor: string;
  items: T[];
}
export interface SidebarItem {
  label: string;
  href: string;
  count?: number;
  current?: boolean;
}
export interface SectionNav {
  title: string;
  items: SidebarItem[];
}
export interface Engine {
  software: string;
  name: string;
  card: Card | undefined;
  category: string;
  count: number;
  mapped: number;
  version: string | undefined;
}
type Section = "data" | "tools" | "operations" | "engines";

const UNSPECIFIED = "Unspecified";
export const UNMAPPED = "Not mapped to an operation yet";

export const slug = (s: string) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "other";

function groupBy<T>(items: T[], label: (t: T) => unknown, last = UNSPECIFIED): Group<T>[] {
  const map = new Map<string, T[]>();
  for (const item of items) {
    const raw = label(item);
    const key = typeof raw === "string" && raw.trim() ? raw : last;
    const list = map.get(key);
    if (list) list.push(item);
    else map.set(key, [item]);
  }
  return [...map.entries()]
    .map(([k, list]) => ({ label: k, anchor: slug(k), items: list }))
    .sort((a, b) =>
      a.label === last ? 1 : b.label === last ? -1 : a.label.localeCompare(b.label, "en"),
    );
}

const cardsOf = (kind: "data" | "tool") =>
  loadRegistry()
    .cards.filter((c) => c.kind === kind)
    .sort(byName);

let memo:
  | { data: Group<Card>[]; tools: Group<Card>[]; operations: Group<Card>[]; engines: Engine[] }
  | undefined;

function all() {
  if (memo) return memo;
  const reg = loadRegistry();
  const toolCards = new Map(cardsOf("tool").map((c) => [c.id, c]));
  const bySoftware = new Map<string, Implementation[]>();
  for (const i of reg.implementations) {
    const list = bySoftware.get(i.software);
    if (list) list.push(i);
    else bySoftware.set(i.software, [i]);
  }
  const engines = [...bySoftware.entries()]
    .map(([software, list]) => {
      const card = toolCards.get(software);
      return {
        software,
        name: card?.name ?? software,
        card,
        category: typeof card?.category === "string" ? card.category : UNSPECIFIED,
        count: list.length,
        mapped: list.filter((i) => i.implements).length,
        version: list[0]?.entry.harvest?.engine_version as string | undefined,
      };
    })
    .sort(byName);
  memo = {
    data: groupBy(cardsOf("data"), (c) => c.region),
    tools: groupBy(cardsOf("tool"), (c) => c.category),
    operations: groupBy([...reg.operations].sort(byName), (c) => c.group),
    engines,
  };
  return memo;
}

export const dataGroups = () => all().data;
export const toolGroups = () => all().tools;
export const operationGroups = () => all().operations;
export const engines = () => all().engines;
export const engineGroups = () => groupBy(all().engines, (e) => e.category);

const operationGroup = (id: string | null) => {
  if (!id) return undefined;
  return loadRegistry().operations.find((o) => o.id === id)?.group as string | undefined;
};

const implMemo = new Map<string, Group<Implementation>[]>();
/** One engine's implementations, grouped by the operation group they implement. */
export function implementationGroups(software: string): Group<Implementation>[] {
  let groups = implMemo.get(software);
  if (!groups) {
    const list = loadRegistry()
      .implementations.filter((i) => i.software === software)
      .sort(byName);
    groups = groupBy(list, (i) => operationGroup(i.implements), UNMAPPED);
    implMemo.set(software, groups);
  }
  return groups;
}

export function implementationGroupOf(i: Implementation): string {
  return operationGroup(i.implements) ?? UNMAPPED;
}

function navItems<T>(path: string, groups: Group<T>[], current?: unknown): SidebarItem[] {
  return groups.map((g) => ({
    label: g.label,
    href: `${path}#${g.anchor}`,
    count: g.items.length,
    current: g.label === current,
  }));
}

/** The left sidebar for a section; `current` marks the group this page belongs to. */
export function sectionNav(section: Section, current?: unknown): SectionNav {
  switch (section) {
    case "data":
      return { title: "Regions", items: navItems(href("data/"), dataGroups(), current) };
    case "tools":
      return { title: "Categories", items: navItems(href("tools/"), toolGroups(), current) };
    case "operations":
      return {
        title: "Operation groups",
        items: navItems(href("operations/"), operationGroups(), current),
      };
    case "engines":
      return {
        title: "Engines",
        items: engines().map((e) => ({
          label: e.software,
          href: enginePath(e.software),
          count: e.count,
          current: e.software === current,
        })),
      };
  }
}

/** The sidebar of one engine's pages: the groups of its implementations. */
export function engineNav(software: string, current?: string): SectionNav {
  return {
    title: software,
    items: navItems(enginePath(software), implementationGroups(software), current),
  };
}

export function projectNav(current: "about" | "ai" | "contribute"): SectionNav {
  return {
    title: "This project",
    items: [
      { label: "About and privacy", href: href("about/"), current: current === "about" },
      { label: "AI skill and connector", href: href("ai/"), current: current === "ai" },
      { label: "Contribute", href: href("contribute/"), current: current === "contribute" },
    ],
  };
}
