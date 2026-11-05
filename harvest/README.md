# Harvesters

Each harvester asks one engine to describe its own tools and writes one
implementation entry per tool to `implementations/<software>/<id>.yaml`. Nobody
types parameter lists by hand, and the same engine version always gives the same
files, so re-harvesting after a release shows exactly what the release changed.

| Harvester | Engine | Reads | Writes |
| --- | --- | --- | --- |
| `gdal.py` | GDAL 3.11 or later | `gdal --json-usage` | `implementations/gdal/` |
| `pdal.py` | PDAL | `pdal --drivers --showjson`, `pdal --options <stage> --showjson` | `implementations/pdal/` |
| `postgis.py` | PostGIS | the database's own catalogue (`pg_proc`) | `implementations/postgis/`, `implementations/postgis-raster/` |
| `python_libs.py` | Shapely, GeoPandas | the installed packages, by introspection | `implementations/shapely/`, `implementations/geopandas/` |

Not yet: DuckDB spatial (its extension downloads from extensions.duckdb.org at
run time), ArcGIS Pro (needs a machine with Pro; see the design set),
QGIS Processing, GRASS and WhiteboxTools.

## What goes in, what stays out

- **In:** names, types, defaults, choices, required flags, value ranges, SQL
  overloads (`signatures`), the engine version, and a documentation link only
  when the engine itself reports one.
- **Out:** the engines' help text. Entries are CC0; engine documentation is under
  its own licence. Summaries, when wanted, are written fresh in mappings.
- **Never:** hand edits. Anything a person adds (which operation a tool
  implements, the crosswalk, differences, effects) goes in
  `mappings/<software>/<id>.yaml` and is merged at build time.

## Running them

The engines come from conda-forge. With micromamba (or conda):

```sh
micromamba create -f harvest/environment.yml          # GDAL, Shapely, GeoPandas
micromamba create -f harvest/environment-pdal.yml     # PDAL
micromamba create -f harvest/environment-postgis.yml  # PostgreSQL + PostGIS

micromamba run -n geo-registry-engines python harvest/gdal.py
micromamba run -n geo-registry-engines python harvest/pdal.py --pdal "$(micromamba run -n geo-registry-pdal which pdal)"
dsn=$(harvest/start-postgis.sh "$(dirname "$(micromamba run -n geo-registry-postgis which psql)")" /tmp/georeg-pg)
micromamba run -n geo-registry-engines python harvest/postgis.py --psql "$(micromamba run -n geo-registry-postgis which psql)" --dsn "$dsn"
micromamba run -n geo-registry-engines python harvest/python_libs.py
```

`start-postgis.sh` starts a throwaway database on a Unix socket only (no network
port); run it as an ordinary user, since PostgreSQL refuses to run as root.

The **Engines** workflow does all of this every Monday against the newest
releases and opens a pull request when anything changed.

## After a re-harvest

`geo-registry validate` checks every mapping against the new files. A mapping
whose implementation disappeared, or whose crosswalk names a parameter the engine
no longer has, fails validation with the file and the parameter, so the pull
request shows what to fix. Then `checks/equivalence.py` runs every mapped
implementation on the same small inputs and compares the results.
