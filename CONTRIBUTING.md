# Contributing to geo-registry

Thanks for helping. The registry is only useful if its entries are correct and its
endpoints answer, so every change is reviewed by a person.

## Ground rules

- One entry per file: `entries/data/<id>.yaml` for data sources, `entries/tools/<id>.yaml`
  for everything else. `id` is lowercase letters, digits and hyphens, and equals the file
  name.
- Entries are dedicated to the public domain under CC0-1.0. Only submit what you are free
  to dedicate. Do not copy publishers' descriptions word for word.
- Never put credentials, API keys, tokens or signed URLs in an entry. Use `auth: api-key`
  (or `oauth` / `login`) and describe how to get access in `notes`.
- Never invent URLs. If you have not opened it, it does not go in.

## Regional stewards

Stewards are volunteers who know the data for an area (a state, a country, a federal
agency family). They review PRs touching their area, keep `last_verified` fresh and
decide when an entry is `degraded` or `retired`. Stewards are listed in `.github/CODEOWNERS`
once appointed. To become one, open an issue naming the area and a few entries you have
reviewed.

## Adding or reviewing a data entry

1. Copy an existing reviewed entry as a template.
2. Replace landing-page links with real endpoints where they exist: `ogc-wfs`, `ogc-wms`,
   `ogc-api-features`, `stac`, `ept`, `arcgis-rest`, `s3`, `download` and so on. Put a layer,
   collection or index name in `index`.
3. Test every `access` URL and paste the result into the PR template's access test.
4. Set `coverage.region` (and `bbox` if you know it), `publisher`, `update`, `formats_out`
   and `last_verified`.
5. Optional: add a `recipe` using one allowed tool and short declarative steps.
6. Set `review.state: reviewed`. Leave `review.source` / `source_row` on seeded entries.

**New hosts need maintainer approval.** If an access URL is on a domain no other entry
uses, say so in the PR. A maintainer confirms the host is the publisher's own or an
established mirror before merging.

## Adding or reviewing an operation

1. One file per operation in `entries/operations/`, named by its id (hyphenated, e.g.
   `zonal-statistics`).
2. One operation per meaning: two engine tools share an operation when the same inputs
   give the same kind of output and their differences fit in parameters or notes. A
   different kind of output is a different operation, linked with `broader`/`narrower`.
3. List in `aka` the names analysts and engines actually use (ArcGIS Pro, QGIS, GRASS,
   PostGIS), so a search by any of them finds it. Write `summary` and `pitfalls` in your
   own words; do not copy vendor help text.
4. If Columbus already runs it, use Columbus's input and parameter names and fill
   `columbus` with its tool and op. Take `checks` ids from Columbus's check catalogue.
5. New operations start as `review.state: draft`. A person who knows the operation in at
   least two engines sets `reviewed`, `reviewed_by` and `reviewed_on`.

Do not write implementation entries by hand; they come from the engine harvesters.

## Mapping an implementation to an operation

1. Find the harvested file, e.g. `implementations/gdal/gdal-vector-clip.yaml`, and read
   its parameters.
2. Create `mappings/<software>/<same id>.yaml` with `id`, `implements`, a `crosswalk`
   for every port and parameter of the operation the engine can take, and `differences`
   in your own words. Use `fixed` or `unsupported` rather than leaving a parameter out
   when the engine cannot honour it; that is how Columbus knows not to drop it silently.
3. A tool whose name suggests an operation it is not gets a mapping with only `notes`.
4. Add or extend a case in `checks/equivalence.py` when the operation has none, and run
   it (see `harvest/README.md` for the engines). Mappings start as `review.state:
   draft`; a person who knows both engines sets `reviewed`.

A mapping may set only `implements`, `crosswalk`, `presets`, `differences`, `effects`,
`requires`, `notes` and `review`; everything else belongs to the harvester.

## Seeded entries and the converter

`seed/convert.py` regenerates all seeded entries from `seed/geospatial-tool-atlas.csv`, and
CI runs `python seed/convert.py --check`. While the seed is the source of truth:

- Fix systematic problems (licence mapping, region inference, slugging) in the converter
  and regenerate: `python seed/convert.py`.
- Fix a single row's facts in the CSV and regenerate. Keep the CSV otherwise verbatim.
- Review a seeded entry with an override: `seed/overrides/<id>.yaml` holds `id` and the
  fields to replace (tested `access` endpoints, `coverage`, `recipe`, `last_verified`;
  `review` is merged, so set `state: reviewed`, `reviewed_by` and `reviewed_on` once a
  person has checked it). Run `python seed/convert.py` and commit both the override and the
  regenerated entry.

## Local checks

```sh
python seed/convert.py --check
cd build
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
cargo run -- validate
cargo run -- build --out ../dist
cargo run -- search "your query" --db ../dist/registry.sqlite
```

## Code

Code contributions (CLI, schema, converter, checks) are licensed under Apache-2.0. Keep
`build/` on stable Rust and the converter on the Python standard library plus PyYAML.
