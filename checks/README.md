# Checks

`index_compat.py` runs in CI on every change: it compares the index built from `main` with
the one built from the change and fails if anything installed Columbus servers read was
altered or removed (see the README, "Index compatibility").

## Health checks

`health.py` probes every data entry's endpoints; the **Health** workflow runs it every
Tuesday and opens a pull request with the changes (`python checks/health.py --apply` does
the same locally). `test_health.py` tests every probe against a local server, in CI.

A failing entry goes from `active` to `degraded`; a degraded entry that answers again goes
back to `active`; `last_verified` is refreshed on success when it is missing or more than
30 days old. Seeded entries change through `seed/overrides/<id>.yaml`, so regenerating the
seed keeps the change.

Each check reads `access[]` from data entries, probes one item, and records the outcome.
A failing entry moves `status` from `active` to `degraded` (never straight to `retired`;
that needs a human PR). `last_verified` is updated only on success.

| access type | check | pass when |
|---|---|---|
| `http`, `api`, `other` | `HEAD`, falling back to ranged `GET`, redirects followed (max 5) | 2xx/3xx final status within 15 s |
| `download` | `HEAD` on the URL; optional ranged `GET` of the first 1 KiB | 2xx and a plausible `Content-Type` / `Content-Length` |
| `ogc-wms`, `ogc-wmts`, `ogc-wfs`, `ogc-wcs` | `GetCapabilities` | valid capabilities XML; the `index` layer/typename, if set, is listed |
| `ogc-api-features`, `ogc-api-tiles` | landing page, `/conformance`, `/collections` | JSON with the expected conformance classes; `index` collection present |
| `stac` | root catalog, then `/collections` (API) or child links (static) | valid STAC JSON; `index` collection resolvable |
| `ept` | fetch `ept.json` (or `index`) | JSON with `bounds`, `points`, `schema`, `srs` |
| `arcgis-rest` | `?f=json` on the service | JSON without an `error` member |
| `s3` | anonymous `ListObjectsV2` with `max-keys=1` on the bucket/prefix | 200 with at least one key |

Rules for the checker:

- Probes are read-only and tiny: no full downloads, no tile sweeps, at most one request
  per host per second, an identifying `User-Agent`, and respect for `robots.txt` and
  published usage policies (e.g. the OSM tile policy).
- `auth: api-key|oauth|login` entries are skipped unless a maintainer configures a
  credential for that host as a CI secret. Credentials never go into entries.
- Results are written to a report artifact, and a bot PR updates `status` / `last_verified`
  in batches so every change is reviewable.
- Checks never execute anything taken from an entry. Recipes are not run by the checker.

Run part of it with `--id ID` (repeatable) or `--type TYPE`; `--report` writes every
result as JSON. It is Python with the standard library and PyYAML, like the converter,
rather than a Rust subcommand as first planned: it needs no build and runs anywhere.
