# Design spec: geo-registry.io

As of 2026-11-07. This file is the only source for the look: every visual value on the site comes from it. The mockups on the design canvas were for choosing, so don't copy their code.

## Direction and rationale

**Direction A, "Reference manual"**, chosen by the owner on 2026-11-07 from three directions. It is documentation-style like MDN or the PostGIS docs: dense tables, square corners, a left sidebar for the section, and one navy accent. The owner asked for serious, trustworthy and dense, with docs sites as the reference.

Kept from the others: nothing from B. From C, only the idea of a dark theme, rebuilt here from A's palette. The dark theme follows the visitor's device setting, and a toggle overrides it.

## Tokens

All colours are CSS custom properties on `:root`. A `[data-theme="dark"]` block and a `@media (prefers-color-scheme: dark)` block both set the dark values; the toggle sets `data-theme` and stores the choice in `localStorage`, wrapped in try/catch. Contrast was checked by script on 2026-11-07, with each ratio measured against the theme's background.

| Token | Light | Dark | Role | Contrast (light / dark) |
|---|---|---|---|---|
| `--color-bg` | `#FFFFFF` | `#111418` | Page background | — |
| `--color-surface` | `#F3F5F8` | `#1A1F26` | Sidebar, table headers, callout grounds | — |
| `--color-text` | `#1A1D21` | `#E7EAEE` | Body text, headings | 16.9 / 15.3 |
| `--color-muted` | `#4F5966` | `#A3ADB8` | Secondary text, breadcrumbs, captions | 7.1 / 8.1 |
| `--color-border` | `#D5DAE1` | `#2E3640` | Table rules, dividers (decorative) | — |
| `--color-border-strong` | `#7A8491` | `#6B7684` | Input and button borders, badge outlines | 3.8 / 4.0 (≥3:1 for controls) |
| `--color-accent` | `#1F4E79` | `#8CB8E6` | Links, primary button, current nav item | 8.7 / 8.9 |
| `--color-accent-hover` | `#163A5B` | `#B3D1F0` | Link and button hover | — |
| `--color-on-accent` | `#FFFFFF` | `#111418` | Text on the primary button | 8.7 / 8.9 |
| `--color-success` | `#1E6B3A` | `#6CC48A` | "Reviewed" badge, endpoint answered | 6.5 / 8.7 |
| `--color-warning` | `#8A5A00` | `#E0B357` | "Seeded / draft / unverified" badge, pitfall callout border | 5.9 / 9.5 |
| `--color-warning-bg` | `#FFF8E8` | `#2B2312` | Pitfall callout ground | text 16.0 / 12.9 |
| `--color-danger` | `#A12B2B` | `#F08A8A` | Retired, endpoint failed, error states | 7.3 / 7.7 |
| `--color-focus` | `#1F4E79` | `#8CB8E6` | 2 px focus outline, 2 px offset | 3:1+ on both |
| Font: body, UI | IBM Plex Sans 400, 600, 700 | | All text except code | SIL OFL; self-host the woff2 files (no Google Fonts request, for privacy) |
| Font: code | IBM Plex Mono 400, 600 | | Ids, tool names, parameter names, YAML | SIL OFL; self-hosted |
| Type scale (px) | 13 · 14 · 16 · 18 · 22 · 28 · 36 | | 13 badges and labels, 14 tables and sidebar, 16 body, 18 summaries, 22 h2, 28 h1 on mobile, 36 h1 | Ratio about 1.25; line height 1.5 for body, 1.2 for headings |
| Section labels | 12 px, 600, uppercase, letter-spacing 0.06em, `--color-muted` | | Sidebar group names | Never used for body text |
| Spacing scale (px) | 4 · 8 · 12 · 16 · 24 · 32 · 40 · 48 · 64 | | Smaller gaps inside a group than between groups | Scale values only |
| Radius | `--radius: 2px` | | Inputs, buttons, badges, callouts | No other radius |
| Shadows | none | | | Separate with borders and surface colour |
| Motion | 150 ms colour transitions only; none with `prefers-reduced-motion` | | | No animated layout |
| Breakpoints (px) | 375 (minimum checked) · 768 (sidebar collapses above/below) · 1280 (full layout) | | | Content column max-width 1100 px |

## Component library

None: plain semantic HTML components built from these tokens, as of 2026-11-07. The site is static Astro pages that need no JavaScript framework. Search uses Pagefind's own UI, restyled with the tokens through its CSS variables. Build each component once as an Astro component: header, search box, sidebar, breadcrumb, badge, callout, data table, facet list, entry header, footer, theme toggle.

## Screens

| Screen | Purpose | Key content |
|---|---|---|
| Home `/` | Start a lookup | Search box first; counts by kind (183 data sources, 1,381 tools, 65 operations, about 6,700 engine implementations, numbers read from the index at build time); browse links by kind, region and theme; one line on what "seeded" vs "reviewed" means; link to the AI skill and connector page |
| Search results `/search/` | Find an entry from a task | Pagefind results with filters: kind, region, theme or category, licence, access type, review state, software (implementations); each result shows name, kind, summary and review badge |
| Data source `/data/<id>/` | Decide whether a source fits | Name, summary, publisher, coverage region (and bbox when present), licence (SPDX plus original text), access endpoints table (type, URL, auth, notes), status, review badge, last verified date, recipe if any, related entries, suggest-a-fix and source-YAML links |
| Tool `/tools/<id>/` | Decide whether a tool fits | Name, summary, category and subcategory, tool kind, licence, open source, language, interfaces and `call`, project status, URL, notes, also-categories, related, review badge |
| Operation `/operations/<id>/` | Know how each engine does a job | As on the canvas: aka, summary, review badge, pitfall callouts, parameters table, inputs and outputs, checks, "In each engine" table (engine, tool link, distance-style key parameter crosswalk, units note, dissolve or other notable parameters, differences), broader, narrower and related |
| Implementation `/implementations/<software>/<id>/` | Exact engine parameters | Engine, tool name, harvested parameters table (name, type, default, choices), SQL overloads where present, the operation it implements with the crosswalk and differences, harvested-on note |
| Browse lists `/data/`, `/tools/`, `/operations/`, `/engines/`, `/engines/<software>/` | Scan a kind | Dense sortable-looking tables (static, ordered by name), grouped by category, region or operation group; the sidebar lists the groups |
| AI page `/ai/` | Install the skill or connector | One section per app: what to download or paste, which plan it needs, the connector URL `https://mcp.geo-registry.io/mcp` |
| Contribute `/contribute/` | Help fix the registry | How to suggest a fix (issue form), how review works (seeded → reviewed), link to CONTRIBUTING.md |
| About and privacy `/about/` | Trust | What the registry is, licences (code Apache-2.0, entries CC0-1.0, upstream terms apply), analytics statement (cookieless, no personal data), not affiliated with any listed publisher |
| 404 | Recover | Search box and links to the browse lists |

Layout: a top bar (site name, search, main nav: Data · Tools · Operations · Engines · Contribute · theme toggle), and below it a left sidebar for the current section plus the content column. Below 768 px the sidebar becomes a "Sections" disclosure button above the content, and the main nav wraps.

## Required states

- **Screens:** empty (a browse list or filter with no results says so and links to clear the filters), loading (the search box shows "Searching…" while Pagefind loads chunks), error (search failed to load: a plain message plus links to the browse lists), success.
- **Controls:** hover, focus, disabled, loading, error.
- **Project-specific states:**
  - **Review badge:** reviewed in the success colour; seeded, draft and harvested in the warning colour. The wording is in the build brief, "Review badges".
  - **Retired or replaced entry:** a danger-coloured banner linking to `replaced_by`.
  - **Missing values:** "Not stated" in muted text, never blank.

## Accessibility checks

WCAG 2.2 AA, checked by tool (axe-core or pa11y in CI on a sample of pages):

- Text contrast 4.5:1; large text, controls and focus rings 3:1.
- Targets at least 24 px; 44 px for the main buttons and the theme toggle.
- Every action works by keyboard, with a visible focus ring.
- Search fields have visible or programmatic labels.
- Tables use `<th scope>`.
- One `<h1>` per page.
- A skip link goes to the content.
- `lang="en"`.

## Do

- Primary button: `--color-accent` background, `--color-on-accent` text, weight 600, radius 2 px, at least 44 px tall.
- Badges: 1 px border in the state colour, text in the same colour, 13 px, weight 600, no fill.
- Pitfall callout: 1 px `--color-warning` border, `--color-warning-bg` ground, the word "Pitfall." in bold, then the text.
- Tables: a 2 px `--color-text` rule under the header and 1 px `--color-border` between rows. Identifiers go in Plex Mono. Wide tables scroll inside an `overflow-x: auto` box.
- Current sidebar item: weight 600, `--color-text`, with a 3 px `--color-accent` left rule.
- Identifiers, tool names, parameter names and URLs: always IBM Plex Mono.
- Real registry content only. Show a missing field as "Not stated".

## Don't

- No gradients, glow, blur, shadows, or any radius other than 2 px.
- No cards for single facts. Group with space and tables; cards only for search results.
- No emoji. Icons only where needed (theme toggle, external link, copy), from one inline-SVG stroke set (Lucide, ISC licence), with `aria-hidden` or `aria-label`.
- No placeholder text as a label, and no low-contrast grey labels.
- No hero sections or marketing blocks. The home page leads with search.
- No Google Fonts or other third-party requests at runtime. The only exception is the Cloudflare Web Analytics script (`static.cloudflareinsights.com`) and its beacon (`cloudflareinsights.com`), build brief, "Analytics and privacy".
- Use references for structure only: never reproduce MDN's or any other site's logo, imagery, copy or colour identity.

## Screenshot check

A screen is done only when screenshots at 375 and 1,280 px wide, in both light and dark, show tokens only, every required state, and nothing overflowing or overlapping. Record the screenshot paths as evidence.
