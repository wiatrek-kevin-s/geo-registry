# Final review: geo-registry.io

## Who runs it and when

One sceptical reviewer in a fresh chat, after every task is done. You didn't build this, so you see what the builder stopped seeing. Read `docs/build-brief.md`, `docs/design-spec.md` and `docs/progress-log.md`, then use the product at https://geo-registry.io, https://mcp.geo-registry.io/mcp and the `skill` release. You fix nothing: you report, and the owner decides.

## Run the product

1. Run every acceptance check in `docs/tasks.json` that you can run; note any that fail now and any you couldn't run, with why.
2. Run the automated audits: the site build and its tests, the connector tests, the skill lint, Prettier and ESLint, `npm audit --omit=dev` in `site/` and `agent/connector/`, a secret scan of the repo history (gitleaks or GitHub's secret scanning results), and axe on the 23 pages in `site/tests/a11y-pages.json` in light and dark.
3. Browser tests of each main flow at 375 and 1,280 px: search from home to an entry, browse by kind and region, open an operation and follow an engine link, suggest a fix, toggle the theme.
4. Negative tests:
   - Bad input: a 0-character, 200-character and 201-character `search`; `limit` 0 and 21; a 17 kB request body; `get_entry` with an unknown id and with a path-traversal id such as `../../x`; a search query containing HTML.
   - A failing service: point the connector at a missing API file and check the error message is plain.
   - Repeated actions: 50 rapid connector calls, and two merges close together (from the CI history).
   - Untrusted text: confirm an entry whose notes contain markup renders as text.
5. Confirm each security baseline item marked applied, including the H-5 settings (ruleset, CODEOWNERS, secret scanning, push protection) and that the production environment is limited to `main`.

Record what you ran and each result, because a review that ran nothing is only opinion.

## Lenses

- **Accessibility:** WCAG 2.2 AA in both themes, keyboard-only use, screen-reader labels on search and the theme toggle.
- **Content:** review badges are honest on every page and in connector results; licences and "Not stated" appear where they should; no invented text.
- **Phone layout:** every screen at 375 px.
- **Privacy:** only the analytics beacon leaves the site; `/about/` says so; the connector logs no request bodies.
- **Speed:** home and an entry page load in under 2 seconds on a throttled 4G profile; a search returns in under 1 second after the first.
- **Security:** the workflow guard, token scope and expiry, untrusted-text handling in the site, the connector and the skill.
- **Correctness:** API files match F-2; counts match `dist/`; URLs match F-1.
- **Failure handling:** what users see when Pagefind, the API or the connector fails.
- **Maintainability:** pinned versions, no unexplained dependencies, the plugin copy check.
- **The intent:** does it serve the intent, and is each success measure S-1 to S-5 met?

**Upkeep:** could the owner follow the runbook in `docs/operations.md` next month, and does every change stream have an owner?

## Scoring

Only findings with a concrete harm scenario count: who is hurt, how, and what triggers it. Score severity and likelihood from 1 to 10 each; priority is severity × likelihood.

| Priority | Label |
|---|---|
| 40 or more, or severity 9+ with likelihood 3+ | Fix now |
| 20 to 39 | Fix when convenient |
| Under 20 | Accept |

Severity guide: 10 data lost or leaked, or money lost; 7 a main flow broken; 4 a workaround needed; 1 cosmetic. Likelihood guide: 10 every user, every time; 5 some users, often; 1 rare and unusual.

## What the person sees

- Three lines: the verdict, the worst risk, and what you recommend.
- One table:

| # | Finding | Harm scenario | Severity | Likelihood | Priority | Label | Suggested fix |
|---|---|---|---|---|---|---|---|

- The recommended fix set: every fix-now finding, plus any cheap fix-when-convenient ones, for the owner to approve or change.

## After the review

The fixes the owner chooses become `R-n` tasks in `docs/tasks.json`, done like any task, with evidence. Then one targeted re-check in a fresh chat, of those fixes only, confirms each one and that nothing next to it broke.
