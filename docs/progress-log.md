# Progress log: geo-registry.io

Kit version 1.0 · as of 2026-11-07, session S1 in progress

## Where things stand

- **Session:** S1 · **Task:** T-1 done (checkpoint: show first pages), T-2 next
- **Next step:** owner looks at the first pages; then T-2 · **Waiting on the owner:** T-1 checkpoint; H-0 and H-2 before T-4
- **Homework received:** none yet

## Decisions

| Date | Decision | Why | Asked or decided |
|---|---|---|---|
| 2026-11-07 | Pinned Node 26.10.0 (current LTS), Astro 7.4.7 (current); Pagefind 1.6.0 comes with T-2 | Brief: pin exact versions with an "as of" date | Decided |
| 2026-11-07 | Simple `/data/`, `/tools/`, `/operations/` lists built in T-1; grouping and `/engines/` stay in T-5 | The top nav and breadcrumbs need targets, or the T-1 link check fails | Decided |
| 2026-11-07 | Operation "In each engine" table shows tool names as code, without implementation links, until T-5 builds those pages | Keeps T-1's link check at 0 broken links | Decided |
| 2026-11-07 | Tests use Node's built-in runner, with dev dependencies `node-html-parser` 9.0.7 and `yaml` 2.9.1 | Fewest dependencies | Decided |
| 2026-11-07 | IBM Plex woff2 files (Sans 400/600/700, Mono 400/600) copied from `@ibm/plex-sans` 1.1.0 and `@ibm/plex-mono` 2.5.0, packages then removed | Their postinstall runs IBM telemetry; the files are all we need | Decided |

## Change requests

| ID | Date | What and why | Options | Recommendation | Status |
|---|---|---|---|---|---|

Status: raised, approved, declined, or Sent to Blueprint (touches a one-way door; affected tasks paused).

## Handoff notes

Newest first, written as you go. Mark each claim verified (checked this session) or unverified.

### S1: T-1 done (2026-11-07)

- **Done:** owner set the repo folder to "Keep Downloaded"; all files local again; no iCloud conflict copies left; `git fsck` clean (verified). T-1 acceptance checks all pass; evidence in `docs/tasks.json` (verified). Added Prettier, ESLint, `astro check` (TypeScript 6.0.3, because `@astrojs/check` 0.9.12 and typescript-eslint 8.72.1 don't support TypeScript 7 yet) and `@types/node` 26.6.6.
- **Watch:** the repo still lives in iCloud Drive. iCloud made conflict copies (`data 2`, `operations 2`) in `site/dist` while downloading; a rebuild removed them. If git errors reappear, check for "dataless" files (`ls -lO`) and conflict copies first.
- **Saved:** branch `site/t1-thin-site`, PR to `main` (not merged).

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
