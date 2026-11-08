# Progress log: geo-registry.io

Kit version 1.0 · as of 2026-11-08, session S2 in progress

## Where things stand

- **Session:** S2 · **Task:** T-5 to T-7 done; T-8 and T-9 partly checked; site live at https://geo-registry.io/
- **Next step:** S2 checkpoint, then S3 · **Waiting on the owner:** Enforce HTTPS, checks 1 to 6
- **Homework received:** H-0 (geo-registry.io, expires 2027-11-07, auto-renew: on), H-1 (except Enforce HTTPS), H-2, H-3 (all checked with gh api)

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
| 2026-11-08 | `/ai/` exists from T-5 as a short "being built" page; T-11 fills it | T-6's accessibility check and the home page need the page; it says plainly that the skill isn't ready | Decided |
| 2026-11-08 | Implementation pages and results get a one-line summary built from real fields (engine, operation, tool name, or the notes) | Implementations have no `summary` field, and "Not stated" on 6,741 results says nothing | Decided |
| 2026-11-08 | The 28 variant implementations cite `mappings/<software>/<id>.yaml` as their source | They exist only as mapping files; every other implementation has a file in `implementations/` | Decided |
| 2026-11-08 | Implementation pages state the harvester and engine version instead of a harvest date | The registry records no date for a harvest | Decided |
| 2026-11-08 | Added dev dependencies stylelint 18.0.0 and @axe-core/playwright 4.14.0 (as of 2026-11-08) | Named by T-6 | Decided |
| 2026-11-08 | Search filters are a "Filters" fold: open on a laptop, closed on a phone unless a filter is set | Ten filters pushed every result below the first screen on a phone | Decided |
| 2026-11-08 | `/engines/` is grouped by the engine's tool category; `/engines/<software>/` by operation group, with unmapped tools last | The spec's "grouped by category, region or operation group" | Decided |

## Change requests

| ID | Date | What and why | Options | Recommendation | Status |
|---|---|---|---|---|---|
| CR-1 | 2026-11-07 | Search misses 3 of 10 lookups (REQ-4, Must). Measured with plain Pagefind relevance: "lidar Travis County" finds nothing (txgio-lidar's page says Texas, not Travis County); "STAC imagery" ranks its first target 31st and "OpenStreetMap" ranks planet-osm 16th, below many tools. (a) Group results by kind (Data sources, Operations, Tools; top 5 each plus "Show all N"); flat list when a kind filter is set. Measured: every lookup then ranks its target 1st to 4th in its group. (b) Place lookup: when a query names a US county, also search with its state; needs a small county-to-state list from the Census Bureau's public-domain Gazetteer file, kept in `site/`, loaded only for such queries. Measured: "lidar Texas" ranks txgio-lidar 1st | Approve both; approve (a) only and drop the Travis lookup from REQ-4; keep the plain list | Approve both | approved 2026-11-07 (owner, in chat) |

Status: raised, approved, declined, or Sent to Blueprint (touches a one-way door; affected tasks paused).

## Handoff notes

Newest first, written as you go. Mark each claim verified (checked this session) or unverified.

### S2: merged and live on geo-registry.io (2026-11-08)

- **Done:** owner did H-1 and H-3 and said "merge 39 to 42". #42 and #41 merged into their stacked branches, #39 and #40 into `main`; #40 waited for its required checks, no admin override. Main run 42517891357: all jobs pass, site deployed (verified). geo-registry.io returns 200 with a valid certificate, www redirects, footer and `meta.json` show commit c642908, 64 browser tests pass on the live domain, the beacon is the only third-party host (verified).
- **Waiting:** owner ticks Enforce HTTPS (T-8), runs checks 1 to 6 (S2 checkpoint). T-9's page-view check is at the start of S3.
- **Check 7 in S2:** page footer and `meta.json` carry the merge commit (verified). The connector and skill zip don't exist yet; the full check is T-21.
- **iCloud:** "… 2" conflict copies are back in the repo folder, untracked; none are in git (verified). Commit with explicit paths until the repo leaves iCloud.
- **Saved:** branch `site/s2-close` (this log and tasks.json).

### S2: T-9 code in PR; waiting on H-1 and H-3 (2026-11-08)

- **Done:** the beacon is added only when `CF_BEACON_TOKEN` is set; a build with a test token loads exactly one third-party script, a build without loads none (verified). Browser tests never reach Cloudflare, so CI won't count as visits. Pages DNS records re-checked against GitHub's docs on 2026-11-08 (verified).
- **Saved:** branch `site/t9-analytics`, stacked on `site/t7-fix-form`. T-8 and T-9 stay `todo` until checked on the live domain.
- **Next:** owner does H-1 and H-3 and says to merge; Claude merges the four PRs in order, then checks T-8 and T-9 on geo-registry.io.

### S2: T-7 in PR (2026-11-08)

- **Done:** issue form `.github/ISSUE_TEMPLATE/fix-entry.yml`, "Suggest a fix" on all four kinds of entry page, label `fix-request` created (verified).
- **Saved:** branch `site/t7-fix-form`, stacked on `site/t6-look`.
- **Next:** T-9's code, then the owner's steps (H-1, H-3).

### S2: T-6 in PR (2026-11-08)

- **Done:** theme toggle, required states, style lint, axe on 23 pages, 24 screenshots. All T-6 checks pass; the site also builds, links and passes every browser test at `SITE_BASE=/` (verified). Screenshots exposed crushed table columns that no automated check caught; fixed.
- **Correction:** the T-6 evidence was first committed while ESLint still reported 3 errors in the theme script. Fixed in the next commit on the branch; lint now exits 0 (verified).
- **For the final review:** on a phone, the "In each engine" table needs a sideways scroll to reach its Parameters and Differences columns, as the spec says for wide tables (verified).
- **Saved:** branch `site/t6-look`, stacked on `site/t5-full-site`.
- **Next:** T-7.

### S2: T-5 in PR (2026-11-08)

- **S1 checkpoint:** owner confirmed checks 1 and 2 on the live site (2026-11-08).
- **Done:** smoke check passed (1,564 entries, 65 operations, 6,741 implementations) (verified). 6,741 implementation pages, `/engines/`, grouped lists with a sidebar, about, contribute, a short `/ai/`, 404 and `/api/v1/`. The build makes 8,436 pages and 25,283 files, 159 MB, in about 16 s (verified). All T-5 checks pass; evidence in `docs/tasks.json` (verified).
- **Saved:** branch `site/t5-full-site`.
- **Next:** T-6.

### S1: T-3 and T-4 done, site live (2026-11-08)

- **Done:** owner confirmed auto-renew on and said "merge 37". Main run 42509313766 deployed the site; both T-4 URLs return 200 and the footer shows commit 21cffb9 (verified). The 34 browser tests (10 lookups at 1280 and 375 px, badges, retired banner) pass against the live site (verified).
- **Note:** the owner saw "site unsecure" because geo-registry.io isn't connected yet; that is T-8 (H-1) in S2.
- **Saved:** branch `site/s1-close` (this log and tasks.json).
- **Next:** S1 checkpoint, then S2.

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
