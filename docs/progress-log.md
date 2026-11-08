# Progress log: geo-registry.io

Kit version 1.0 · as of 2026-11-07, session S1 in progress

## Where things stand

- **Session:** S1 · **Task:** T-1 and T-2 done and merged (#35, #36); T-3 evidence recorded (auto-renew to confirm); T-4 in PR #37
- **Next step:** owner approves merging #37, then the S1 checkpoint · **Waiting on the owner:** merge of #37, auto-renew confirmation, checkpoint checks 1 and 2
- **Homework received:** H-0 (domain bought, 2026-11-08; expiry read from the public record), H-2 (done by the owner, checked with gh api)

## Decisions

| Date | Decision | Why | Asked or decided |
|---|---|---|---|
| 2026-11-07 | Pinned Node 26.10.0 (current LTS), Astro 7.4.7 (current); Pagefind 1.6.0 comes with T-2 | Brief: pin exact versions with an "as of" date | Decided |
| 2026-11-07 | Simple `/data/`, `/tools/`, `/operations/` lists built in T-1; grouping and `/engines/` stay in T-5 | The top nav and breadcrumbs need targets, or the T-1 link check fails | Decided |
| 2026-11-07 | Operation "In each engine" table shows tool names as code, without implementation links, until T-5 builds those pages | Keeps T-1's link check at 0 broken links | Decided |
| 2026-11-07 | Tests use Node's built-in runner, with dev dependencies `node-html-parser` 9.0.7 and `yaml` 2.9.1 | Fewest dependencies | Decided |
| 2026-11-07 | IBM Plex woff2 files (Sans 400/600/700, Mono 400/600) copied from `@ibm/plex-sans` 1.1.0 and `@ibm/plex-mono` 2.5.0, packages then removed | Their postinstall runs IBM telemetry; the files are all we need | Decided |
| 2026-11-07 | Search page uses Pagefind's JS API with our own result list, not Pagefind's default UI | REQ-5 needs a review badge on every result, which the default UI can't show; the spec's intent (Pagefind, restyled with tokens) is kept | Decided |
| 2026-11-07 | Retired entries: weight 0.3 on their pages and, in results, searched after active and degraded entries (relevance order kept within each) | The 0.3 weight alone still ranked tiger-line-road-features above census-tiger-line for "TIGER/Line"; REQ-6 says retired rank below active | Decided |
| 2026-11-07 | Tests serve `dist/` with a small Node server (`site/scripts/serve.mjs`) | Astro 7's `astro preview` detaches, so Playwright can't manage it | Decided |
| 2026-11-08 | Started T-4 before the owner confirmed H-0's auto-renew | T-4 needs only H-2, which is verified; the owner asked to be contacted only when input is truly needed | Decided |

## Change requests

| ID | Date | What and why | Options | Recommendation | Status |
|---|---|---|---|---|---|
| CR-1 | 2026-11-07 | Search misses 3 of 10 lookups (REQ-4, Must). Measured with plain Pagefind relevance: "lidar Travis County" finds nothing (txgio-lidar's page says Texas, not Travis County); "STAC imagery" ranks its first target 31st and "OpenStreetMap" ranks planet-osm 16th, below many tools. (a) Group results by kind (Data sources, Operations, Tools; top 5 each plus "Show all N"); flat list when a kind filter is set. Measured: every lookup then ranks its target 1st to 4th in its group. (b) Place lookup: when a query names a US county, also search with its state; needs a small county-to-state list from the Census Bureau's public-domain Gazetteer file, kept in `site/`, loaded only for such queries. Measured: "lidar Texas" ranks txgio-lidar 1st | Approve both; approve (a) only and drop the Travis lookup from REQ-4; keep the plain list | Approve both | approved 2026-11-07 (owner, in chat) |

Status: raised, approved, declined, or Sent to Blueprint (touches a one-way door; affected tasks paused).

## Handoff notes

Newest first, written as you go. Mark each claim verified (checked this session) or unverified.

### S1: T-3 recorded, T-4 in PR (2026-11-08)

- **Done:** owner merged #35 and #36; main CI green (runs 42507342363, 42507365333) (verified). H-2 settings checked with `gh api` (verified). Domain registered at Cloudflare, expires 2027-11-07 (verified via whois); auto-renew not yet confirmed, so T-3 stays `todo`.
- **T-4:** `site-check` and `site-deploy` added to `ci.yml`, existing jobs unchanged; PR #37. PR run 42507879342 and dispatch run 42508573110: all jobs pass, deploy skipped (verified). Last check (live fetch) waits for the merge.
- **Owner preference:** contact only at hard stops (merge approvals, checkpoints, homework), batched in one message.
- **iCloud:** five "… 2" sync-conflict copies were moved out of the repo to the session scratchpad; the committed versions are current.

### S1: T-2 done (2026-11-07)

- **Done:** Pagefind search with filters, review badges on pages and results, retired banner and ranking, escaped registry text. CR-1 approved by the owner and built: results grouped by kind (top 5 each, "Show all"), county lookup from the Census 2025 Gazetteer (`site/public/places/us-counties.json`, rebuilt by `site/scripts/build-counties.mjs`). All T-2 checks pass; evidence in `docs/tasks.json` (verified).
- **Saved:** branch `site/t2-search`, PR stacked on the T-1 PR #35 (not merged).
- **Next:** H-0 and H-2 from the owner (T-3), then T-4.

### S1: T-1 done (2026-11-07)

- **Done:** owner set the repo folder to "Keep Downloaded"; all files local again; no iCloud conflict copies left; `git fsck` clean (verified). T-1 acceptance checks all pass; evidence in `docs/tasks.json` (verified). Added Prettier, ESLint, `astro check` (TypeScript 6.0.3, because `@astrojs/check` 0.9.12 and typescript-eslint 8.72.1 don't support TypeScript 7 yet) and `@types/node` 26.6.6.
- **Watch:** the repo still lives in iCloud Drive. iCloud made conflict copies (`data 2`, `operations 2`) in `site/dist` while downloading; a rebuild removed them. If git errors reappear, check for "dataless" files (`ls -lO`) and conflict copies first.
- **Saved:** branch `site/t1-thin-site`, PR #35 to `main` (not merged).

### S1 in progress (2026-11-07)

- **Done:** smoke check passed (registry build: 1,564 entries, 65 operations, 6,741 implementations; verified). `site/` scaffolded on branch `site/t1-thin-site` (from `origin/main` 0e69646): loader, layout, tokens, data/tool/operation pages, home, three lists, link checker, T-1 unit test. Build makes 1,633 pages in about 1 s (verified). Link check: 0 broken at `/geo-registry/` (16,888 links) and at `/` (verified); it fails correctly when a page and a font are deleted (verified).
- **Blocker:** the repo lives in iCloud-synced `~/Documents` and macOS has offloaded files ("dataless"), e.g. `.git/packed-refs`, `README.md`, `entries/tools/pdal.yaml`. In Claude's sandbox these read as empty, so git and the T-1 unit test fail. Owner asked to keep the folder downloaded or move it out of iCloud.
- **Saved:** nothing committed yet (git blocked). Files are on disk in `site/`.
- **Next:** after the fix, run `npm run test:unit` in `site/`, record T-1 evidence, commit, push, open the PR; show the owner the first pages (checkpoint).

### Planning → S1 (2026-11-07)

- **Done:** kit delivered after planning with Blueprint; nothing built yet.
- **Decisions and deviations:** none beyond the brief.
- **Loose ends:** open questions Q-1 to Q-5 in the brief.
- **Saved:** the kit files in this repository.
- **Next:** start S1 with T-1; ask the owner for H-2 early so T-4 isn't blocked.
