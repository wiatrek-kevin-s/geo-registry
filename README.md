# geo-registry

The public registry behind **Columbus**, an open-source governed GIS MCP server. Each GIS
tool or data source is one small YAML file. A Rust CLI validates the files and builds a
searchable index (`index.json` and `registry.sqlite`) that the Columbus server downloads
to answer "what data covers this place?" and "which tool does this job?".

The registry was seeded from the *Geospatial Tool Atlas* (1,564 rows: 183 data sources,
1,381 tools). Every seeded entry is marked `review.state: seeded` until a person checks it.

## Layout

```
entries/data/<id>.yaml      data sources (atlas kind "Data source")
entries/tools/<id>.yaml     libraries, applications, servers, formats, services, ...
schema/entry.schema.json    JSON Schema (2020-12) for both kinds
seed/geospatial-tool-atlas.csv   the seed spreadsheet, kept verbatim
seed/convert.py             reproducible CSV -> entries converter (Python 3.12+, PyYAML)
build/                      Rust crate "geo-registry": validate, build, search
checks/                     planned per-access-type health checks (not running yet)
.github/                    CI and the pull request template
```

## Using the CLI

```sh
cd build
cargo run --release -- validate                     # schema + ids + references
cargo run --release -- build --out ../dist          # index.json, registry.sqlite, index.sha256
cargo run --release -- search lidar --kind data --db ../dist/registry.sqlite
```

`validate` exits non-zero and prints one line per problem (`file: message`). It checks the
schema, that `id` equals the file name, that ids are unique, that `related` and
`replaced_by` resolve, that each file sits in the directory for its `kind`, and that a
recipe names an allowed Columbus tool.

`build` validates first, then writes:

- `index.json`: `{format_version, generated_at, count, entries: [card, ...]}`. A card has id,
  kind, name, summary, themes or category, region, license, access types, status, url and
  review state.
- `registry.sqlite`: table `entries` (card and full entry as JSON) and FTS5 table
  `entries_fts` over name, summary, category, themes and notes.
- `index.sha256`: `sha256sum -c` manifest of both files. Signing is a TODO.

Set `SOURCE_DATE_EPOCH` for a reproducible `generated_at`.

## Example entries

A data entry, as generated from the atlas:

```yaml
id: txgio-lidar
kind: data
name: TxGIO lidar
summary: Texas lidar point clouds and DEMs collected under StratMap and partners.
publisher: Texas Geographic Information Office
themes:
- texas
- open-data-sources
coverage:
  region: Texas
license: LicenseRef-Public-Domain
license_original: Public domain
access:
- type: http
  url: https://www.geographic.texas.gov/stratmap/elevation-lidar.html
  auth: none
status: active
review:
  state: seeded
  source: geospatial-tool-atlas
  source_row: 1336
```

A tool entry:

```yaml
id: pdal
kind: tool
name: PDAL
category: Core libraries & formats
subcategory: Data access & IO
tool_kind: Library
summary: Point cloud translation and processing library with JSON pipelines and CLI.
open_source: 'yes'
license: BSD-3-Clause
language: C++
interfaces:
- C/C++
- Python
- CLI
call:
- python
- cli
- c-cpp
wrapped_by_columbus: false
project_status: active
url: https://pdal.io
notes: Agent can run PDAL pipelines.
also_categories:
- Point clouds, LiDAR & 3D
status: active
review:
  state: seeded
  source: geospatial-tool-atlas
  source_row: 69
```

`call` lists how an agent can drive the tool. `wrapped_by_columbus` turns true once the
Columbus server ships a governed wrapper for it. `project_status` is the upstream project's
health. `status` is the health of the entry itself.

## Seeded vs reviewed

| | `seeded` | `reviewed` |
|---|---|---|
| Source | `seed/convert.py` from the atlas row in `review.source_row` | a person, through a PR |
| `access` | the atlas URL, usually a landing page (`type: http`) | real endpoints (`ogc-wfs`, `stac`, `ept`, ...) that were tested |
| `coverage`, `publisher` | inferred conservatively, often `Unspecified` / `Unknown` | checked against the publisher |
| `recipe`, `last_verified` | absent | present where useful |

The Columbus server can show seeded entries but should treat them as leads, not
verified sources. To review one, fix the fields, test each access URL, set
`last_verified`, and change `review.state` to `reviewed`. Leave `source` and
`source_row` in place.

Until the seed is retired, `entries/` must match `python seed/convert.py` output, and CI
fails on drift. To review a seeded entry, change the converter (or move the entry out of
the seed set with an override) in the same PR. See CONTRIBUTING.md.

## Recipes are declarative

A data entry may carry a `recipe`: the Columbus tool to use (`query_features`,
`vector_op`, `raster_op`, `pointcloud_pipeline` or `registry_fetch`) and a few
plain-language steps. Recipes are never code. The schema rejects shell, scripts and
inline programs in steps, and the server only maps steps onto its own audited
operations. Adding an access URL on a **host not already in the registry needs
maintainer approval**, because the server may fetch from any host listed here.

## Contributing

Contributions go through pull requests. The template asks for an **access test**: the
command you ran against each URL, what came back, and the date. **Regional stewards** look
after entries for their area (for example Texas, or the US federal sources) and review PRs
that touch it. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licences

- Code (`build/`, `seed/convert.py`, `schema/`, CI): [Apache-2.0](LICENSE).
- Entries (`entries/`) and the generated index: [CC0-1.0](LICENSE-ENTRIES), dedicated to
  the public domain.
- The `license` field inside an entry describes the upstream tool or dataset, not this
  repository. Values are SPDX expressions where the atlas was unambiguous. Otherwise
  they are `LicenseRef-*` (e.g. `LicenseRef-Proprietary`, `LicenseRef-Public-Domain`,
  `LicenseRef-Multiple`) or `NOASSERTION`. The atlas text is kept in `license_original`
  whenever it was changed. Always check the publisher's terms before use.
