// Search page: Pagefind's JS API with our own result list, so every result can
// show its review badge. Registry text is set with textContent only.
// Results are grouped by kind unless a kind filter is chosen (change request CR-1).
import { expandCounty, MIGHT_NAME_COUNTY, type Gazetteer } from "./places";

const BASE = import.meta.env.BASE_URL.endsWith("/")
  ? import.meta.env.BASE_URL
  : `${import.meta.env.BASE_URL}/`;
const PAGE_SIZE = 10;
const GROUP_SIZE = 5;
/** Registry statuses in ranking order: retired entries rank last. */
const STATUS_ORDER = ["active", "degraded", "retired"];

const REVIEW_TEXT: Record<string, string> = {
  reviewed: "Reviewed by a person",
  seeded: "Unverified lead from the seed atlas",
  draft: "Draft: written, not yet checked by a person",
  harvested: "Harvested from the engine, not yet checked by a person",
};

// Kind filter values (lib/search.ts KIND_LABEL) in the order groups appear.
const GROUPS: [string, string, string][] = [
  ["Data source", "data source", "data sources"],
  ["Operation", "operation", "operations"],
  ["Tool", "tool", "tools"],
  ["Implementation", "implementation", "implementations"],
];

// Filter keys in display order, with their labels (design spec, search screen).
const FILTERS: [string, string][] = [
  ["kind", "Kind"],
  ["region", "Region"],
  ["theme", "Theme"],
  ["category", "Category"],
  ["group", "Operation group"],
  ["licence", "Licence"],
  ["access", "Access type"],
  ["review", "Review state"],
  ["software", "Software"],
  ["status", "Status"],
];

interface PagefindResult {
  id: string;
  data: () => Promise<{ url: string; meta: Record<string, string> }>;
}
interface Pagefind {
  options: (o: Record<string, unknown>) => Promise<void>;
  init: () => Promise<void>;
  filters: () => Promise<Record<string, Record<string, number>>>;
  search: (
    q: string | null,
    o?: { filters?: Record<string, string> },
  ) => Promise<{ results: PagefindResult[] }>;
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Record<string, string> = {},
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

function badge(review: string, reviewedOn?: string): HTMLElement {
  const known = review in REVIEW_TEXT;
  const label = known ? REVIEW_TEXT[review] : "Review state not stated";
  return el(
    "span",
    { class: `badge badge-${known ? review : "unknown"}`, "data-review": review },
    review === "reviewed" && reviewedOn ? `${label}, ${reviewedOn}` : label,
  );
}

const KIND_TEXT: Record<string, string> = {
  data: "Data source",
  tool: "Tool",
  operation: "Operation",
  implementation: "Implementation",
};

async function card(r: PagefindResult, headingTag: "h2" | "h3"): Promise<HTMLLIElement> {
  const d = await r.data();
  const m = d.meta;
  const li = el("li", { class: "result", "data-id": m.id ?? "", "data-kind": m.kind ?? "" });
  const h = el(headingTag, { class: "result-title" });
  h.append(el("a", { href: d.url }, m.title ?? m.id ?? d.url));
  li.append(h);
  const meta = el("div", { class: "result-meta" });
  meta.append(el("span", {}, KIND_TEXT[m.kind] ?? m.kind ?? ""));
  meta.append(el("code", {}, m.id ?? ""));
  meta.append(badge(m.review ?? "", m.reviewed_on));
  if (m.status === "retired") meta.append(el("span", { class: "badge badge-retired" }, "Retired"));
  li.append(meta);
  li.append(m.summary ? el("p", {}, m.summary) : el("p", { class: "not-stated" }, "Not stated"));
  return li;
}

let gazetteer: Promise<Gazetteer | null> | undefined;
function loadGazetteer(): Promise<Gazetteer | null> {
  gazetteer ??= fetch(`${BASE}places/us-counties.json`)
    .then((r) => (r.ok ? (r.json() as Promise<Gazetteer>) : null))
    .catch(() => null);
  return gazetteer;
}

export async function startSearch(): Promise<void> {
  const form = document.getElementById("search-form") as HTMLFormElement;
  const input = document.getElementById("q") as HTMLInputElement;
  const status = document.getElementById("search-status") as HTMLElement;
  const box = document.getElementById("results") as HTMLElement;
  const errorBox = document.getElementById("search-error") as HTMLElement;
  const filterBox = document.getElementById("filters") as HTMLElement;
  const setState = (s: string) => (document.body.dataset.searchState = s);

  const params = new URLSearchParams(location.search);
  input.value = params.get("q") ?? "";
  const selected: Record<string, string> = {};
  for (const [key] of FILTERS) {
    const v = params.get(key);
    if (v) selected[key] = v;
  }

  status.textContent = "Searching…";
  setState("loading");
  let pagefind: Pagefind;
  try {
    pagefind = (await import(/* @vite-ignore */ `${BASE}pagefind/pagefind.js`)) as Pagefind;
    await pagefind.options({ baseUrl: BASE });
    await pagefind.init();
  } catch {
    status.textContent = "";
    errorBox.hidden = false;
    setState("error");
    return;
  }

  const selects: Record<string, HTMLSelectElement> = {};
  const available = await pagefind.filters();
  for (const [key, label] of FILTERS) {
    const values = available[key];
    if (!values || Object.keys(values).length === 0) continue;
    const id = `filter-${key}`;
    const wrap = el("div", { class: "filter" });
    wrap.append(el("label", { for: id }, label));
    const select = el("select", { id, name: key });
    select.append(el("option", { value: "" }, "Any"));
    for (const v of Object.keys(values).sort((a, b) => a.localeCompare(b))) {
      const opt = el("option", { value: v }, v);
      if (selected[key] === v) opt.selected = true;
      select.append(opt);
    }
    select.addEventListener("change", () => setFilter(key, select.value));
    selects[key] = select;
    wrap.append(select);
    filterBox.append(wrap);
  }
  filterBox.hidden = false;

  function setFilter(key: string, value: string): void {
    if (value) selected[key] = value;
    else delete selected[key];
    if (selects[key]) selects[key].value = value;
    run();
  }

  function queryString(extra: Record<string, string> = {}): string {
    const p = new URLSearchParams();
    if (input.value.trim()) p.set("q", input.value.trim());
    for (const [k, v] of Object.entries({ ...selected, ...extra })) if (v) p.set(k, v);
    const qs = p.toString();
    return qs ? `?${qs}` : location.pathname;
  }

  /**
   * Results for the query plus its county expansions, original matches first.
   * Retired entries always come last (REQ-6): each status tier is searched in
   * turn, keeping Pagefind's relevance order within it.
   */
  async function searchAll(
    queries: (string | null)[],
    filters: Record<string, string>,
  ): Promise<PagefindResult[]> {
    const tiers = filters.status ? [filters.status] : STATUS_ORDER;
    const seen = new Set<string>();
    const out: PagefindResult[] = [];
    for (const status of tiers) {
      for (const q of queries) {
        const res = await pagefind.search(q, { filters: { ...filters, status } });
        for (const r of res.results) {
          if (!seen.has(r.id)) {
            seen.add(r.id);
            out.push(r);
          }
        }
      }
    }
    return out;
  }

  let runId = 0;
  async function run(): Promise<void> {
    const mine = ++runId;
    const q = input.value.trim();
    history.replaceState(null, "", queryString());
    box.replaceChildren();
    const hasFilters = Object.keys(selected).length > 0;
    if (!q && !hasFilters) {
      status.textContent = "Type what you are looking for, such as “lidar Texas” or “buffer”.";
      setState("idle");
      return;
    }
    status.textContent = "Searching…";
    setState("loading");

    const queries: (string | null)[] = [q || null];
    if (q && MIGHT_NAME_COUNTY.test(q)) {
      const gaz = await loadGazetteer();
      if (gaz) queries.push(...expandCounty(q, gaz));
    }

    const groups = selected.kind ? GROUPS.filter((g) => g[0] === selected.kind) : GROUPS;
    const found = await Promise.all(
      groups.map(async (g) => ({
        group: g,
        results: await searchAll(queries, { ...selected, kind: g[0] }),
      })),
    );
    if (mine !== runId) return;
    const total = found.reduce((n, f) => n + f.results.length, 0);

    if (total === 0) {
      status.replaceChildren(
        document.createTextNode(
          hasFilters ? "No entries match these filters. " : "No entries match this search. ",
        ),
      );
      if (hasFilters) {
        const clear = el("a", { href: q ? `?q=${encodeURIComponent(q)}` : "?" }, "Clear filters");
        clear.addEventListener("click", (ev) => {
          ev.preventDefault();
          for (const k of Object.keys(selected)) delete selected[k];
          for (const s of Object.values(selects)) s.value = "";
          run();
        });
        status.append(clear);
      }
      setState("empty");
      return;
    }

    const parts = found
      .filter((f) => f.results.length)
      .map(
        (f) =>
          `${f.results.length.toLocaleString("en-US")} ${f.results.length === 1 ? f.group[1] : f.group[2]}`,
      );
    status.textContent = `${total.toLocaleString("en-US")} ${total === 1 ? "result" : "results"}: ${parts.join(", ")}`;

    if (selected.kind) {
      // One flat list, paged.
      const { results } = found[0]!;
      const list = el("ol", { class: "results" });
      const more = el("button", { type: "button", class: "button-secondary" }, "Show more results");
      let shown = 0;
      const next = async () => {
        const batch = results.slice(shown, shown + PAGE_SIZE);
        list.append(...(await Promise.all(batch.map((r) => card(r, "h2")))));
        shown += batch.length;
        more.hidden = shown >= results.length;
      };
      more.addEventListener("click", next);
      box.append(list, more);
      await next();
    } else {
      for (const f of found) {
        if (!f.results.length) continue;
        const [kind, , plural] = f.group;
        const section = el("section", { class: "result-group", "data-group": kind });
        const title = plural.charAt(0).toUpperCase() + plural.slice(1);
        section.append(el("h2", {}, `${title} (${f.results.length.toLocaleString("en-US")})`));
        const list = el("ol", { class: "results" });
        list.append(
          ...(await Promise.all(f.results.slice(0, GROUP_SIZE).map((r) => card(r, "h3")))),
        );
        section.append(list);
        if (f.results.length > GROUP_SIZE) {
          const all = el(
            "a",
            { href: queryString({ kind }), class: "show-all" },
            `Show all ${f.results.length.toLocaleString("en-US")} ${plural}`,
          );
          all.addEventListener("click", (ev) => {
            ev.preventDefault();
            setFilter("kind", kind);
          });
          section.append(all);
        }
        box.append(section);
      }
    }
    if (mine !== runId) return;
    setState("done");
  }

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    run();
  });
  await run();
}
