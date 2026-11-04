## What this changes

<!-- New entry, update, retirement, schema/tooling change? Name the entry ids. -->

- Entry id(s):
- Kind: data / tool / tooling

## Access test (required for data entries)

<!-- Paste what you ran and what came back, for every `access` item you added or changed.
     Example: `curl -sI <url>` status line, a GetCapabilities excerpt, a STAC `/collections`
     count, or `pdal info --summary` on one EPT tile. No credentials or API keys. -->

```
command:
result:
date tested (YYYY-MM-DD):
```

- [ ] Every `access[].url` was opened on the date above and returned what the entry says
- [ ] `last_verified` is set to that date
- [ ] Any new host (domain not already in the registry) is flagged below for maintainer approval

New hosts:

## Checklist

- [ ] `geo-registry validate` passes locally (`cd build && cargo run -- validate`)
- [ ] `recipe` (if any) uses only `query_features`, `vector_op`, `raster_op`, `pointcloud_pipeline` or `registry_fetch`, and its steps are plain declarative sentences, not code
- [ ] Licence is an SPDX id/expression, a `LicenseRef-*`, or `NOASSERTION`, and matches the publisher's terms
- [ ] `review.state` is `reviewed` only if I checked the fields above against the source
- [ ] Regional steward for this area tagged (see CONTRIBUTING.md), if there is one
- [ ] I dedicate my contribution to entries/ under CC0-1.0
