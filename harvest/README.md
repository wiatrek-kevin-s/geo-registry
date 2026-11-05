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
| `qgis.py` | QGIS Processing (all providers) | `qgis_process --json list` and `--json help` | `implementations/qgis/` |
| `grass.py` | GRASS | each module's `--interface-description`, in a throwaway session | `implementations/grass/` |
| `whitebox.py` | WhiteboxTools | `--listtools` and `--toolparameters` | `implementations/whiteboxtools/` |
| `python_packages.py` | about 40 Python packages listed in `python-packages.yml` (rasterio, pyproj, the PySAL family, osmnx, momepy, movingpandas, Apache Sedona's SQL functions, ...) | the installed packages, by introspection | `implementations/<software>/` |
| `r_packages.py` | R: sf, terra | each exported function's formals (and each S4 method's) | `implementations/sf/`, `implementations/terra/` |
| `turf.py` | Turf.js | its TypeScript declarations, read with TypeScript 5's parser (Turf is not run) | `implementations/turf-js/` |
| `cli_packages.py` | TauDEM, LAStools (open programs) | the conda package's file list; by name only | `implementations/taudem/`, `implementations/lastools/` |
| `duckdb_spatial.py` | DuckDB spatial extension | `duckdb_functions()` before and after `LOAD spatial` | `implementations/duckdb-spatial-extension/` |
| `rustgis.py` | RustGIS | `rustgis.Session().tools()` (PyPI package) | `implementations/rustgis/` |
| `arcgis_pro_export.py` + `arcgis_pro.py` | ArcGIS Pro | ArcPy (`ListTools`, `GetParameterInfo`), on a machine with Pro | `implementations/arcgis-pro/` |

DuckDB spatial and RustGIS run only in the Engines workflow: DuckDB downloads its
extension at run time, and RustGIS is run there rather than on maintainers' machines.
Their implementations appear with the first weekly harvest (or Actions → Engines →
Run workflow).

## Not harvested yet, and why

| What | Why |
| --- | --- |
| ArcGIS Pro | needs one run of the export on a machine with Pro, and the Esri terms question settled |
| SAGA GIS, Orfeo ToolBox | not on conda-forge for Linux; need another install route |
| Oracle Spatial, SQL Server spatial | closed engines: to be read from a live database's catalogue, or entered by hand |
| mapclassify, spglm, spint, harmonica, salem, regionmask | no software entry in the registry yet (the seed atlas lacks them) |
| scikit-mobility | does not import with Shapely 2 (it uses the removed `cascaded_union`) |
| r5py, geowombat, xESMF | need Java or very large dependencies; left out of the Python environment for now |
| Whitebox Workflows, ArcGIS API for Python, Google Earth Engine | proprietary or service APIs: tools run on a vendor's servers or need an account |
| TauDEM and LAStools parameters | their programs print free-form usage, so only their names are recorded |

LAStools from conda-forge is the open part of the suite from 2017 (`lastools 20171231`);
the licensed LAStools programs are not included.

## ArcGIS Pro

ArcGIS Pro cannot run in CI, so its harvest has two halves. On a Windows machine
with Pro, run the export in Pro's own Python (it needs nothing installed, opens no
data and changes nothing):

```bat
"%PROGRAMFILES%\ArcGIS\Pro\bin\Python\Scripts\propy.bat" harvest\arcgis_pro_export.py
```

That writes `arcgis-pro-tools.jsonl`. Then, anywhere with the engines environment:

```sh
python harvest/arcgis_pro.py arcgis-pro-tools.jsonl
```

Re-run both after each Pro release. Only tool and parameter names, types,
defaults and choices are exported; no Esri help text.

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

micromamba create -f harvest/environment-qgis.yml       # then: python harvest/qgis.py --qgis-process <path>
micromamba create -f harvest/environment-grass.yml      # then: python harvest/grass.py --grass <path>
micromamba create -f harvest/environment-whitebox.yml   # then: python harvest/whitebox.py --wbt <path>
micromamba create -f harvest/environment-python.yml     # then, with its Python: python harvest/python_packages.py
micromamba create -f harvest/environment-r.yml          # then: python harvest/r_packages.py --rscript <path>
micromamba create -f harvest/environment-cli.yml        # then: python harvest/cli_packages.py --prefix <env>
npm install --ignore-scripts --prefix /tmp/turf @turf/turf typescript@5   # then: python harvest/turf.py --node-modules /tmp/turf/node_modules
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
