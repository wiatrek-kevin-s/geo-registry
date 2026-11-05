#!/usr/bin/env python3
"""Run each mapped implementation on the same small input and check the results agree.

    python checks/equivalence.py DIST [--gdal PATH] [--psql PATH --dsn CONNINFO]
        [--qgis-process PATH] [--wbt PATH] [--rscript PATH] [--grass PATH] [--turf NODE_MODULES]

DIST is a built registry (registry.sqlite). For every case below, each
implementation mapped to the case's operation is called through its
crosswalk, exactly as Columbus would translate the canonical parameters,
and a measure of the result (area, length, count, coordinates) is compared
with the expected value or, where there is no closed form, with the other
engines' results. A wrong crosswalk (a parameter mapped to the wrong
argument, a unit or value translated wrongly) shows up as a failure; an
engine that cannot honour a canonical value (`unsupported`, `fixed`) is
reported as skipped with the reason, which is the documented difference.
A behaviour difference these tests found and the mapping records (a smoothed
contour, a grid one cell short) is listed in KNOWN_DIFFERENCES and reported as
"differs" with the reason, not as a failure.

Engines not available on this machine are skipped. Needs geopandas and
shapely in the running Python (rasterio, rioxarray, xarray-spatial, rasterstats
and dask-geopandas there too, when installed); GDAL through --gdal; PostGIS
through --psql; R's sf and terra through --rscript; GRASS through --grass; Turf.js
through --turf (a node_modules folder) and node.
Exit status: 0 when nothing failed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import math
import statistics
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import shapely
from shapely import wkt

CRS = "EPSG:32614"  # UTM zone 14N: metres, so canonical unit m is the CRS unit
SRID = 32614


def poly(x0, y0, x1, y1):
    return shapely.box(x0, y0, x1, y1)


# Inside, across the edge of, and outside a 100 m mask.
SELECT_SQUARES = [poly(10, 10, 20, 20), poly(90, 90, 110, 110), poly(200, 200, 210, 210)]
L_SHAPE = shapely.Polygon([(0, 0), (20, 0), (20, 10), (10, 10), (10, 20), (0, 20)])  # area 300; hull 350


@dataclass
class Case:
    operation: str
    title: str
    inputs: dict[str, Any]          # port -> list of geometries, or a DataFrame for tables
    params: dict[str, Any]          # canonical parameters
    measure: str                    # area | length | count | coords | raster_* | field_* | value:<name>
    expected: float | None = None   # None: compare engines with each other
    tolerance: float = 1e-6         # relative
    attrs: dict[str, list] = field(default_factory=dict)  # extra columns per port


CASES = [
    Case("buffer", "100 m square buffered by 10 m", {"layer": [poly(0, 0, 100, 100)]},
         {"distance": 10, "unit": "m", "segments": 8}, "area",
         expected=100 * 100 + 4 * 100 * 10 + math.pi * 10 ** 2, tolerance=0.005),
    Case("buffer", "buffer dissolved into one shape", {"layer": [poly(0, 0, 10, 10), poly(15, 0, 25, 10)]},
         {"distance": 5, "unit": "m", "dissolve": True}, "count", expected=1),
    # Same datum (WGS 84) on both sides: a datum change (to NAD 83, say) depends on
    # which transformation each engine's PROJ setup picks, which is not what this checks.
    Case("reproject", "a point to EPSG:3857 (same datum)", {"layer": [shapely.Point(621000, 3349000)]},
         {"crs": "EPSG:3857"}, "coords", tolerance=1e-9),
    Case("simplify", "zigzag line, tolerance 1 m", {"layer": [shapely.LineString(
         [(0, 0), (10, 0.5), (20, 0), (30, 0.4), (40, 0), (50, 5), (60, 0)])]},
         {"tolerance": 1, "unit": "m"}, "length", tolerance=1e-9),
    Case("make-valid", "bow-tie polygon", {"layer": [shapely.Polygon([(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)])]},
         {}, "area", expected=50.0),
    Case("clip", "square clipped by an overlapping square", {"layer": [poly(0, 0, 100, 100)], "mask": [poly(50, 50, 150, 150)]},
         {}, "area", expected=2500.0),
    Case("dissolve", "two touching squares, same value", {"layer": [poly(0, 0, 10, 10), poly(10, 0, 20, 10)]},
         {"by": "k"}, "count", expected=1, attrs={"layer": {"k": ["a", "a"]}}),
    Case("dissolve", "dissolved area", {"layer": [poly(0, 0, 10, 10), poly(10, 0, 20, 10)]},
         {"by": "k"}, "area", expected=200.0, attrs={"layer": {"k": ["a", "a"]}}),
    Case("dissolve", "everything into one shape (no by)", {"layer": [poly(0, 0, 10, 10), poly(10, 0, 20, 10)]},
         {}, "area", expected=200.0),
    Case("intersect", "overlap of two squares", {"a": [poly(0, 0, 10, 10)], "b": [poly(5, 5, 15, 15)]},
         {}, "area", expected=25.0),
    # Inside the UTM zone, so engines that work in longitude/latitude (Turf) round-trip exactly.
    Case("centroid", "centroid of a 100 m square", {"layer": [poly(621000, 3349000, 621100, 3349100)]}, {}, "coords",
         expected=621050 + 3349050, tolerance=1e-9),
    Case("centroid", "L-shaped polygon, point inside", {"layer": [L_SHAPE]}, {"inside": True}, "count", expected=1),
    Case("convex-hull", "L-shaped polygon", {"layer": [L_SHAPE]}, {}, "area", expected=350.0),
    Case("difference", "square minus an overlapping square", {"layer": [poly(0, 0, 100, 100)], "mask": [poly(50, 50, 150, 150)]},
         {}, "area", expected=7500.0),
    Case("multipart-to-singlepart", "one feature of two squares", {"layer": [shapely.MultiPolygon([poly(0, 0, 10, 10), poly(20, 0, 30, 10)])]},
         {}, "count", expected=2),
    Case("nearest-join", "point joined to the nearer of two points", {"left": [shapely.Point(0, 0)],
         "right": [shapely.Point(3, 4), shapely.Point(10, 10)]}, {}, "field_v", expected=1.0,
         attrs={"right": {"v": [1.0, 2.0]}}),
    Case("merge-layers", "one layer of one square and one of two", {"layers": [[poly(0, 0, 10, 10)],
         [poly(20, 0, 30, 10), poly(40, 0, 50, 10)]]}, {}, "count", expected=3),
    Case("union-overlay", "two overlapping squares: three pieces", {"a": [poly(0, 0, 100, 100)], "b": [poly(50, 50, 150, 150)]},
         {}, "count", expected=3),
    Case("union-overlay", "pieces cover both squares", {"a": [poly(0, 0, 100, 100)], "b": [poly(50, 50, 150, 150)]},
         {}, "area", expected=17500.0),
    Case("symmetric-difference", "two overlapping squares minus their overlap",
         {"a": [poly(0, 0, 100, 100)], "b": [poly(50, 50, 150, 150)]}, {}, "area", expected=15000.0),
    Case("count-points-in-polygon", "two of three points inside", {"polygons": [poly(0, 0, 100, 100)],
         "points": [shapely.Point(10, 10), shapely.Point(50, 50), shapely.Point(200, 200)]}, {"field": "npts"},
         "field_npts", expected=2.0),
    Case("select-by-location", "squares that intersect the mask", {"layer": SELECT_SQUARES, "mask": [poly(0, 0, 100, 100)]},
         {"predicate": "intersects"}, "count", expected=2),
    Case("select-by-location", "squares within the mask", {"layer": SELECT_SQUARES, "mask": [poly(0, 0, 100, 100)]},
         {"predicate": "within"}, "count", expected=1),
    Case("voronoi", "three points, three polygons", {"layer": [shapely.Point(621000, 3349000), shapely.Point(621100, 3349000),
         shapely.Point(621050, 3349080)]}, {}, "count", expected=3),
    Case("polygons-to-lines", "outline of a 100 m square", {"layer": [poly(0, 0, 100, 100)]}, {}, "length", expected=400.0),
    Case("lines-to-polygons", "closed square line", {"layer": [shapely.LineString([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])]},
         {}, "area", expected=10000.0),
    Case("measure-area", "a 100 m square", {"layer": [poly(621000, 3349000, 621100, 3349100)]}, {}, "value:area",
         expected=10000.0, tolerance=0.002),
    Case("measure-length", "a 500 m line", {"layer": [shapely.LineString([(621000, 3349000), (621300, 3349400)])]}, {},
         "value:length", expected=500.0, tolerance=0.002),
    Case("create-grid", "10 m cells over a 100 m square", {"layer": [poly(0, 0, 100, 100)]}, {"cell_size": 10}, "count",
         expected=100),
    Case("table-to-points", "two rows of coordinates",
         {"table": pd.DataFrame({"x": [621000.0, 621010.0], "y": [3349000.0, 3349020.0]})},
         {"x_field": "x", "y_field": "y", "crs": CRS}, "coords",
         expected=621000 + 3349000 + 621010 + 3349020, tolerance=1e-12),
]


# A 20 x 20 elevation raster of 10 m cells: a plane rising 1 m per 10 m to the east,
# so slope is atan(0.1) everywhere, aspect is 270 (facing west), and the mean
# elevation of any column band is known.
DEM_ORIGIN = (621000.0, 3349200.0)
DEM_CELL = 10.0
DEM_SIZE = 20
DEM_NODATA = -9999.0


def dem_values():
    return [[0.1 * (DEM_CELL * c + DEM_CELL / 2) for c in range(DEM_SIZE)] for _ in range(DEM_SIZE)]


def dem_box(col0, col1, row0=0, row1=DEM_SIZE):
    """A polygon over whole cells: columns col0..col1-1 and rows row0..row1-1 (row 0 at the top)."""
    x0, y1 = DEM_ORIGIN
    return poly(x0 + col0 * DEM_CELL, y1 - row1 * DEM_CELL, x0 + col1 * DEM_CELL, y1 - row0 * DEM_CELL)


RASTER = "raster"  # marker: this input is the DEM
RASTER_WEST, RASTER_EAST = "raster:west", "raster:east"  # its western and eastern 10 columns

RASTER_CASES = [
    Case("slope", "plane rising 1 m in 10 m", {"raster": RASTER}, {"units": "degrees", "z_unit": "m"},
         "raster_median", expected=math.degrees(math.atan(0.1)), tolerance=1e-4),
    Case("slope", "same plane, in percent", {"raster": RASTER}, {"units": "percent", "z_unit": "m"},
         "raster_median", expected=10.0, tolerance=1e-4),
    Case("aspect", "plane facing west", {"raster": RASTER}, {}, "raster_median", expected=270.0, tolerance=1e-4),
    Case("hillshade", "plane lit from the north-west", {"raster": RASTER},
         {"z_unit": "m", "azimuth": 315, "altitude": 45}, "raster_median", tolerance=0.01),
    Case("clip-raster", "mask over 10 columns and 16 rows, inside the raster",
         {"raster": RASTER, "mask": [dem_box(0, 10, 2, 18)]}, {}, "raster_count", expected=160.0),
    Case("reproject-raster", "to EPSG:3081, nearest", {"raster": RASTER},
         {"crs": "EPSG:3081", "resampling": "nearest"}, "raster_mean", tolerance=0.02),
    Case("zonal-statistics", "mean over the first 5 columns", {"raster": RASTER, "zones": [dem_box(0, 5)]},
         {"stats": "mean"}, "field_mean", expected=2.5, tolerance=1e-6),
    Case("contour", "plane, every 5 m: three straight lines", {"raster": RASTER}, {"interval": 5}, "count", expected=3),
    Case("contour", "their total length", {"raster": RASTER}, {"interval": 5}, "length", tolerance=0.05),
    Case("resample-raster", "10 m cells to 20 m, average", {"raster": RASTER}, {"resolution": 20, "resampling": "average"},
         "raster_count", expected=100.0),
    Case("resample-raster", "average keeps the mean", {"raster": RASTER}, {"resolution": 20, "resampling": "average"},
         "raster_mean", expected=10.0, tolerance=1e-6),
    Case("mosaic", "west and east halves back together", {"rasters": [RASTER_WEST, RASTER_EAST]}, {},
         "raster_count", expected=400.0),
    Case("mosaic", "values unchanged", {"rasters": [RASTER_WEST, RASTER_EAST]}, {}, "raster_mean", expected=10.0,
         tolerance=1e-6),
    Case("rasterize", "50 m by 30 m rectangle at 10 m cells", {"layer": [dem_box(0, 5, 0, 3)]},
         {"resolution": 10}, "raster_count", expected=15.0),
    # The DEM's 20 columns each hold one value (0.5, 1.5, ... 19.5), so 20 strips.
    Case("raster-to-polygons", "one polygon per column of equal values", {"raster": RASTER}, {}, "count", expected=20),
    Case("raster-to-polygons", "polygons cover the raster", {"raster": RASTER}, {}, "area",
         expected=(DEM_CELL * DEM_SIZE) ** 2, tolerance=1e-9),
]


# Documented output differences the tests convert before comparing, so they still
# check the substance: implementation id -> (factor, what it means).
OUTPUT_SCALE = {
    "whiteboxtools-hillshade": (255 / 32767, "output is 0 to 32767, compared as 0 to 255"),
    "xrspatial-hillshade": (255, "output is illumination from 0 to 1, compared as 0 to 255"),
}


def tabular(case: "Case") -> bool:
    """Cases measured from attributes or returned numbers rather than from geometries."""
    return case.measure.startswith(("field_", "value:"))


class Unsupported(Exception):
    """The implementation cannot honour this case's canonical values (a documented difference)."""


# ---------------------------------------------------------------- translation

def translate(impl: dict, op: dict, case: Case) -> tuple[dict, dict]:
    """Canonical ports and parameters -> engine arguments, through the crosswalk.
    Returns (ports: canonical port -> engine name or None for `self`, args: engine name -> value)."""
    cw = impl.get("crosswalk") or {}
    defaults = {k: v.get("default") for k, v in (op.get("parameters") or {}).items()}
    ports: dict[str, str | None] = {}
    method = impl["call"]["interface"] == "python" and any(
        c in impl["call"]["name"] for c in (".GeoSeries.", ".GeoDataFrame.", ".RasterArray."))
    first_input = op["inputs"][0]["name"]
    eparams = impl.get("parameters") or {}
    for port in [p["name"] for p in op["inputs"] + op["outputs"]]:
        item = cw.get(port)
        if isinstance(item, dict) and "param" in item:
            item = item["param"]
        if isinstance(item, str):
            etype = str((eparams.get(item) or {}).get("type", "")).lower()
            data = case.inputs.get(port)
            if isinstance(data, list) and not is_many(data) and "raster" in etype and "vector" not in etype:
                raise Unsupported(f"'{port}' must be a raster for this engine, not polygons")
            ports[port] = item
        elif port == first_input and method:
            ports[port] = None  # the object the method is called on
        elif isinstance(case.inputs.get(port), pd.DataFrame) and impl["call"]["interface"] in ("python", "sql"):
            continue  # a table read through its columns' values (pass: values, or SQL columns)
        elif port in case.inputs:
            raise Unsupported(f"no mapping for input '{port}'")
    args: dict[str, Any] = {}
    for name, value in case.params.items():
        item = cw.get(name)
        if item is None:
            if value == defaults.get(name):
                continue
            raise Unsupported(f"no mapping for {name}={value!r}")
        if isinstance(item, str):
            args[item] = value
            continue
        if "fixed" in item:
            fixed = item["fixed"]
            if fixed == value or (fixed == "crs-units" and value in ("m", "m2")):
                continue
            raise Unsupported(f"{name}={value!r}: the engine always uses {fixed!r}")
        if "param" not in item:
            if value == defaults.get(name):
                continue
            raise Unsupported(f"{name}={value!r}: {item.get('note', 'no direct argument')}")
        if value in (item.get("unsupported") or []):
            raise Unsupported(f"{name}={value!r} is not supported")
        key = str(value).lower() if isinstance(value, bool) else value
        mapped = (item.get("values") or {}).get(key, value) if isinstance(key, (str, int, float)) else value
        if item.get("pass") == "values":
            mapped = ("values", mapped)
        if item.get("repeat"):
            mapped = [mapped] * item["repeat"]
        args[item["param"]] = mapped
    args.update(impl.get("presets") or {})
    return ports, args


def table_values(case: Case, column: str) -> list:
    table = next(v for v in case.inputs.values() if isinstance(v, pd.DataFrame))
    return list(table[column])


# ------------------------------------------------------------------ runners

def run_python(impl: dict, op: dict, case: Case) -> list:
    ports, args = translate(impl, op, case)
    parts = impl["call"]["name"].split(".")
    frames = {}
    for port, geoms in case.inputs.items():
        if isinstance(geoms, pd.DataFrame):
            frames[port] = geoms
        else:
            frames[port] = gpd.GeoDataFrame(case.attrs.get(port, {}), geometry=list(geoms), crs=CRS)
    kwargs = {}
    for k, v in args.items():
        kwargs[k] = table_values(case, v[1]) if isinstance(v, tuple) and v[0] == "values" else v
    self_obj = None
    for port, engine in ports.items():
        if port not in frames:
            continue
        frame = frames[port]
        if engine is None:
            self_obj = frame if parts[-2] == "GeoDataFrame" else frame.geometry
        elif parts[0] == "shapely":
            kwargs[engine] = frame.geometry.values if len(frame) > 1 or engine == "geometries" else frame.geometry.iloc[0]
        else:
            kwargs[engine] = frame
    if self_obj is not None:
        attr = getattr(self_obj, parts[-1])
        result = attr(**kwargs) if callable(attr) else attr  # .centroid, .convex_hull are properties
    else:
        mod = importlib.import_module(parts[0])
        result = getattr(mod, parts[-1])(**kwargs)
    if tabular(case) and isinstance(result, pd.DataFrame):
        return result
    if case.measure.startswith("value:"):  # .area, shapely.length: numbers, one per feature
        import numpy as np
        return [float(x) for x in np.ravel(np.asarray(result, dtype=float))]
    return geometries(result)


def geometries(result) -> list:
    if isinstance(result, gpd.GeoDataFrame):
        return [g for g in result.geometry if g is not None]
    if isinstance(result, (gpd.GeoSeries, gpd.array.GeometryArray)):
        return [g for g in result if g is not None]
    if isinstance(result, shapely.Geometry):
        return [result]
    return [g for g in list(result) if g is not None]


# Real behaviour differences found by these tests and recorded on the mappings: the run is
# reported as "differs" with the reason instead of failing. (implementation id, case title)
KNOWN_DIFFERENCES = {
    ("whiteboxtools-contours-from-raster", "their total length"):
        "smooths and simplifies contours by default, which shortens them",
    ("whiteboxtools-mosaic", "west and east halves back together"):
        "the output grid is one row and one column short of the inputs' combined extent",
    ("whiteboxtools-mosaic", "values unchanged"):
        "the output grid is one row and one column short of the inputs' combined extent",
    ("gdal-vector-rasterize", "50 m by 30 m rectangle at 10 m cells"):
        "with a resolution and no extent, the grid starts half a cell outside the features",
}


def stage_inputs(tmp: str, ports: dict, op: dict, case: Case, vector_ext: str) -> dict[str, Any]:
    """Write each input to a file; returns canonical port -> path (outputs get fresh paths)."""
    paths = {}
    for port, engine in ports.items():
        if engine is None:
            continue
        data = case.inputs.get(port)
        if data is None:
            if port in [p["name"] for p in op["outputs"]]:
                raster_out = op["outputs"][0]["type"] == "raster"
                paths[port] = str(Path(tmp) / ("out.tif" if raster_out else f"out{vector_ext}"))
            continue
        if is_many(data):
            paths[port] = [write_input(Path(tmp) / f"{port}{i}", d, case, port, vector_ext) for i, d in enumerate(data)]
        else:
            paths[port] = write_input(Path(tmp) / port, data, case, port, vector_ext)
    return paths


def read_output(path: str, op: dict, case: Case):
    if op["outputs"][0]["type"] == "raster":
        return read_raster(Path(path))
    if tabular(case):
        return gpd.read_file(path)
    return [g for g in gpd.read_file(path).geometry if g is not None]


def run_qgis(qp: str, impl: dict, op: dict, case: Case):
    ports, args = translate(impl, op, case)
    with tempfile.TemporaryDirectory() as tmp:
        paths = stage_inputs(tmp, ports, op, case, ".gpkg")
        argv = [qp, "run", impl["call"]["name"], "--"]
        for port, path in paths.items():
            for one in (path if isinstance(path, list) else [path]):  # a multilayer parameter repeats
                argv.append(f"{ports[port]}={one}")
        for k, v in args.items():
            if isinstance(v, bool):
                v = "true" if v else "false"
            argv.append(f"{k}={v}")
        import os
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
               "PATH": str(Path(qp).resolve().parent) + os.pathsep + os.environ.get("PATH", "")}
        r = subprocess.run(argv, capture_output=True, text=True, env=env)
        out = next((paths[p["name"]] for p in op["outputs"] if p["name"] in paths), None)
        if r.returncode != 0 or not out or not Path(out).exists():
            raise RuntimeError(f"qgis_process {impl['call']['name']} failed: {(r.stderr or r.stdout).strip()[-300:]}")
        return read_output(out, op, case)


def run_whitebox(wbt: str, impl: dict, op: dict, case: Case):
    ports, args = translate(impl, op, case)
    with tempfile.TemporaryDirectory() as tmp:
        paths = stage_inputs(tmp, ports, op, case, ".shp")
        argv = [wbt, f"--run={impl['call']['name']}"]
        for port, path in paths.items():
            argv.append(f"--{ports[port]}=" + (";".join(path) if isinstance(path, list) else path))
        for k, v in args.items():
            if isinstance(v, bool):
                if v:
                    argv.append(f"--{k}")
            else:
                argv.append(f"--{k}={v}")
        r = subprocess.run(argv, capture_output=True, text=True)
        out = next((paths[p["name"]] for p in op["outputs"] if p["name"] in paths), None)
        if out is None and r.returncode == 0:  # tools that add fields to their input (PolygonArea)
            out = next(v for p, v in paths.items() if isinstance(v, str) and p in case.inputs)
        if r.returncode != 0 or not out or not Path(out).exists():
            raise RuntimeError(f"whitebox {impl['call']['name']} failed: {(r.stderr or r.stdout).strip()[-300:]}")
        return read_output(out, op, case)


PYLIB_SOFTWARE = {"rasterio", "rioxarray", "xarray-spatial", "rasterstats", "dask-geopandas"}


def valid_cells(arr, nodata=None) -> list[float]:
    return [float(v) for v in arr.ravel() if math.isfinite(v) and (nodata is None or v != nodata)]


def run_pylib(impl: dict, op: dict, case: Case):
    """Python libraries called on arrays or rasters rather than GeoDataFrames."""
    ports, args = translate(impl, op, case)
    name, software = impl["call"]["name"], impl["software"]
    fn = name.split(".")[-1]

    def frame(port):
        return gpd.GeoDataFrame(case.attrs.get(port, {}), geometry=list(case.inputs[port]), crs=CRS)

    def shapes(port):
        return [shapely.geometry.mapping(g) for g in case.inputs[port]]

    if "resampling" in args:
        from rasterio.enums import Resampling
        args["resampling"] = Resampling(args["resampling"])
    if software == "dask-geopandas":
        import dask_geopandas
        kwargs = dict(args)
        for port, engine in ports.items():
            if port in case.inputs:  # clip's mask must stay an ordinary GeoDataFrame
                kwargs[engine] = frame(port) if port == "mask" else dask_geopandas.from_geopandas(frame(port), npartitions=1)
        return geometries(getattr(dask_geopandas, fn)(**kwargs).compute())
    if name == "rasterio.warp.transform_geom":
        import rasterio.warp
        out = rasterio.warp.transform_geom(src_crs=CRS, **{ports["layer"]: shapes("layer")}, **args)
        return [shapely.geometry.shape(g) for g in out]
    with tempfile.TemporaryDirectory() as tmp:
        dem = Path(tmp) / "dem.tif"
        write_dem(dem)
        many = {port: [write_input(Path(tmp) / f"{port}{i}", d, case, port, ".gpkg") for i, d in enumerate(data)]
                for port, data in case.inputs.items() if is_many(data)}
        if software == "rasterio" and name == "rasterio.merge.merge":
            import rasterio.merge
            arr, _ = rasterio.merge.merge(**{ports[p]: paths for p, paths in many.items()}, **args)
            return valid_cells(arr[0], DEM_NODATA)
        if software == "rasterio":
            import rasterio
            import rasterio.mask
            import rasterio.warp
            with rasterio.open(dem) as ds:
                if name == "rasterio.mask.mask":
                    arr, _ = rasterio.mask.mask(**{ports["raster"]: ds, ports["mask"]: shapes("mask")}, **args)
                    return valid_cells(arr[0], ds.nodata)
                if name == "rasterio.features.shapes":
                    import rasterio.features
                    band = ds.read(1)
                    pairs = rasterio.features.shapes(**{ports["raster"]: band}, mask=band != ds.nodata,
                                                     transform=ds.transform, **args)
                    return [shapely.geometry.shape(g) for g, _ in pairs]
                if name == "rasterio.warp.reproject":
                    arr, _ = rasterio.warp.reproject(**{ports["raster"]: ds.read(1)}, src_transform=ds.transform,
                                                     src_crs=ds.crs, src_nodata=ds.nodata, dst_nodata=ds.nodata, **args)
                    return valid_cells(arr, ds.nodata)
        if software == "rasterstats":
            import rasterstats
            rows = list(getattr(rasterstats, fn)(**{ports["zones"]: shapes("zones"), ports["raster"]: str(dem)}, **args))
            return pd.DataFrame(rows)
        import rioxarray
        da = rioxarray.open_rasterio(dem, masked=True).squeeze("band", drop=True)
        arrays = {ports[p]: [rioxarray.open_rasterio(x, masked=True).squeeze("band", drop=True) for x in paths]
                  for p, paths in many.items()}
        if arrays:
            mod = importlib.import_module(name.rsplit(".", 1)[0])
            return valid_cells(getattr(mod, fn)(**arrays, **args).values)
        if software == "rioxarray":
            kwargs = dict(args)
            if "mask" in ports:
                kwargs[ports["mask"]] = shapes("mask")
            return valid_cells(getattr(da.rio, fn)(**kwargs).values)
        if software == "xarray-spatial":
            import xrspatial
            if fn == "zonal_stats":
                from rasterio.features import rasterize
                zones = da.copy(data=rasterize([(g, 1) for g in case.inputs["zones"]], out_shape=da.shape,
                                               transform=da.rio.transform(), fill=0).astype("float64"))
                stats = args.pop("stats_funcs", None)
                kwargs = {ports["zones"]: zones, ports["raster"]: da, **args}
                if stats is not None:
                    kwargs["stats_funcs"] = [stats] if isinstance(stats, str) else stats
                table = xrspatial.zonal_stats(**kwargs)
                return table[table["zone"] == 1].reset_index(drop=True)
            if fn == "contours":
                raise Unsupported("levels must be listed; no interval argument")
            return valid_cells(getattr(xrspatial, fn)(**{ports["raster"]: da}, **args).values)
    raise Unsupported(f"no runner for {name}")


def r_value(v) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return "c(" + ", ".join(r_value(x) for x in v) + ")"
    return json.dumps(str(v))


R_FUNCTION_ARGS = {"join"}  # arguments that take a function (sf::st_join's predicate), not text

R_WRITE = """
if (inherits(res, "SpatRaster")) terra::writeRaster(res, "out.tif", overwrite = TRUE) else
if (inherits(res, "SpatVector")) terra::writeVector(res, "out.gpkg", overwrite = TRUE) else
if (inherits(res, c("sf", "sfc"))) sf::st_write(res, "out.gpkg", quiet = TRUE) else
write.csv(as.data.frame(res), "out.csv", row.names = FALSE)
"""


def run_r(rscript: str, impl: dict, op: dict, case: Case):
    """R packages (sf, terra): inputs written to files, the function called through Rscript."""
    ports, args = translate(impl, op, case)
    read_vector = "sf::st_read({}, quiet = TRUE)" if impl["software"] == "sf" else "terra::vect({})"
    with tempfile.TemporaryDirectory() as tmp:
        call = []
        for port, engine in ports.items():
            if engine is None or port not in case.inputs:
                continue
            data = case.inputs[port]
            if is_many(data):
                # terra::mosaic(x, y, ...): the first in x, the second in y, the rest unnamed
                exprs = [f"terra::rast({json.dumps(write_input(Path(tmp) / f'{port}{i}', d, case, port, '.gpkg'))})"
                         if is_raster(d) else read_vector.format(json.dumps(write_input(
                             Path(tmp) / f"{port}{i}", d, case, port, ".gpkg"))) for i, d in enumerate(data)]
                if engine != "x":
                    raise Unsupported(f"no R calling convention for a list in '{engine}'")
                call += [f"x = {exprs[0]}", f"y = {exprs[1]}", *exprs[2:]]
                continue
            if is_raster(data):
                path = Path(tmp) / f"{port}.tif"
                write_dem(path, data)
                expr = f"terra::rast({json.dumps(str(path))})"
            elif isinstance(data, pd.DataFrame):
                path = Path(tmp) / f"{port}.csv"
                data.to_csv(path, index=False)
                expr = f"read.csv({json.dumps(str(path))})"
            else:
                path = Path(tmp) / f"{port}.gpkg"
                frame = gpd.GeoDataFrame(case.attrs.get(port, {}), geometry=list(data), crs=CRS)
                frame.to_file(path)
                expr = read_vector.format(json.dumps(str(path)))
            call.append(f"`{engine}` = {expr}")
        for k, v in args.items():
            call.append(f"`{k}` = " + (f"sf::{v}" if k in R_FUNCTION_ARGS else r_value(v)))
        script = Path(tmp) / "run.R"
        script.write_text("suppressPackageStartupMessages({library(sf); library(terra)})\n"
                          f"res <- {impl['call']['name']}({', '.join(call)})\n" + R_WRITE)
        r = subprocess.run([rscript, "--vanilla", str(script)], capture_output=True, text=True, cwd=tmp)
        if r.returncode != 0:
            raise RuntimeError(f"{impl['call']['name']} failed: {(r.stderr or r.stdout).strip()[-300:]}")
        if (Path(tmp) / "out.tif").exists():
            return read_raster(Path(tmp) / "out.tif")
        if (Path(tmp) / "out.gpkg").exists():
            out = gpd.read_file(Path(tmp) / "out.gpkg")
            return out if tabular(case) else [g for g in out.geometry if g is not None]
        table = pd.read_csv(Path(tmp) / "out.csv")
        stat = case.measure[len("field_"):]
        if case.measure.startswith("field_") and not any(c.lower().endswith(stat) for c in table.columns):
            table = table.rename(columns={table.columns[-1]: stat})  # terra::zonal names the column after the layer
        return table


def is_raster(data) -> bool:
    return isinstance(data, str) and data.startswith(RASTER)


def is_many(data) -> bool:
    """A list of inputs for a `many` port: raster markers, or lists of geometries."""
    return isinstance(data, list) and bool(data) and (is_raster(data[0]) or isinstance(data[0], list))


def write_input(path_stem: Path, data, case: Case, port: str, vector_ext: str) -> str:
    """Write one input (the DEM or part of it, a table, or geometries); returns its path."""
    if is_raster(data):
        path = path_stem.with_suffix(".tif")
        write_dem(path, data)
    elif isinstance(data, pd.DataFrame):
        path = path_stem.with_suffix(".csv")
        data.to_csv(path, index=False)
    else:
        path = path_stem.with_suffix(vector_ext)
        attrs = case.attrs.get(port, {}) if not is_many(case.inputs.get(port)) else {}
        gpd.GeoDataFrame(attrs, geometry=list(data), crs=CRS).to_file(path)
    return str(path)


# GRASS modules that update an input map's attribute table instead of making a layer,
# which the runner does not reproduce.
GRASS_TABLE_MODULES = {"v.db.join": "joins a database table into the map's own attribute table",
                       "v.distance": "uploads into the from map's attribute table (upload, column)"}


def run_grass(grass: str, impl: dict, op: dict, case: Case):
    """GRASS: a throwaway project in the fixtures' CRS; inputs imported, the computational
    region set from them (and from `resolution`, which GRASS takes from the region), the
    module run through its crosswalk, the result exported."""
    module = impl["call"]["name"]
    if module in GRASS_TABLE_MODULES:
        raise Unsupported(GRASS_TABLE_MODULES[module])
    params = dict(case.params)
    region_res = None
    cw = impl.get("crosswalk") or {}
    if "resolution" in params and isinstance(cw.get("resolution"), dict) and "param" not in cw["resolution"]:
        region_res = params.pop("resolution")  # g.region res=...
    ports, args = translate(impl, op, Case(case.operation, case.title, case.inputs, params, case.measure,
                                           case.expected, case.tolerance, case.attrs))
    out_port = next((p["name"] for p in op["outputs"] if ports.get(p["name"])), None)
    raster_out = op["outputs"][0]["type"] == "raster"
    with tempfile.TemporaryDirectory() as tmp:
        lines = ["set -e"]
        rasters, vectors, call = [], [], []
        for port, engine in ports.items():
            data = case.inputs.get(port)
            if data is None or engine is None:
                continue
            names = []
            for i, d in enumerate(data if is_many(data) else [data]):
                name = f"{port}{i}"
                path = write_input(Path(tmp) / name, d, case, port, ".gpkg")
                if is_raster(d):
                    lines.append(f"r.in.gdal --quiet input={path} output={name}")
                    rasters.append(name)
                else:
                    lines.append(f"v.in.ogr --quiet input={path} output={name}")
                    vectors.append(name)
                names.append(name)
            call.append(f"{engine}={','.join(names)}")
        region = f"raster={','.join(rasters)}" if rasters else f"vector={','.join(vectors)}"
        lines.append(f"g.region {region}" + (f" res={region_res} -a" if region_res else ""))
        if out_port:
            call.append(f"{ports[out_port]}=result")
        flags = ""
        for k, v in args.items():
            if k.startswith("flag_"):
                flags += k[len("flag_"):] if v else ""
            elif isinstance(v, list):
                call.append(f"{k}={','.join(str(x) for x in v)}")
            else:
                call.append(f"{k}={str(v).lower() if isinstance(v, bool) else v}")
        lines.append(f"{module} --quiet {'-' + flags + ' ' if flags else ''}" + " ".join(call))
        result = "result" if out_port else (vectors or rasters)[0]  # in-place modules: the updated map
        out = Path(tmp) / ("out.tif" if raster_out else "out.gpkg")
        if raster_out:
            lines.append(f"r.out.gdal --quiet input={result} output={out} format=GTiff")
        else:
            lines.append(f"v.out.ogr --quiet input={result} output={out} format=GPKG")
        script = Path(tmp) / "run.sh"
        script.write_text("\n".join(lines) + "\n")
        import os
        env = {**os.environ}
        proj = Path(grass).resolve().parent.parent / "share" / "proj"
        if proj.exists():
            env["PROJ_DATA"] = str(proj)
        r = subprocess.run([grass, "--tmp-project", f"EPSG:{SRID}", "--exec", "bash", str(script)],
                           capture_output=True, text=True, env=env, cwd=tmp)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"{module} failed: {(r.stderr or r.stdout).strip()[-300:]}")
        if raster_out:
            return read_raster(out)
        frame = gpd.read_file(out)
        return frame if tabular(case) else [g for g in frame.geometry if g is not None]


TURF_SCRIPT = r"""
const turf = require(process.argv[2]);
const req = JSON.parse(require("fs").readFileSync(0, "utf8"));
const args = [];
const options = {};
for (const [name, value] of req.args) {
  if (name.startsWith("options.")) options[name.slice(8)] = value;
  else args.push(value);
}
if (Object.keys(options).length) args.push(options);
let out = turf[req.fn](...args);
if (out && out.type === "Feature") out = turf.featureCollection([out]);
else if (out && out.type && out.type !== "FeatureCollection") out = turf.featureCollection([turf.feature(out)]);
process.stdout.write(JSON.stringify(out));
"""


def run_turf(node: str, modules: str, impl: dict, op: dict, case: Case):
    """Turf.js through Node: inputs reprojected to WGS 84 GeoJSON (Turf works in longitude and
    latitude), the function called with arguments in the order Turf declares them, the result
    reprojected back to the fixtures' CRS for measuring."""
    cw = impl.get("crosswalk") or {}
    for name, item in cw.items():  # Turf's coordinate units are degrees, never the fixtures' metres
        if isinstance(item, dict) and item.get("fixed") == "crs-units" and name in case.params:
            raise Unsupported(f"{name}: Turf takes degrees here; convert the value first")
    ports, args = translate(impl, op, case)
    order = list((impl.get("parameters") or {}).keys())
    values = {}
    declared = impl.get("parameters") or {}
    for port, engine in ports.items():
        if engine and port in case.inputs:
            frame = gpd.GeoDataFrame(case.attrs.get(port, {}), geometry=list(case.inputs[port]), crs=CRS)
            fc = json.loads(frame.to_crs(4326).to_json(drop_id=True))
            etype = str((declared.get(engine) or {}).get("type", ""))
            if etype.startswith("Feature<") and "FeatureCollection" not in etype:  # one feature per call
                if len(fc["features"]) != 1:
                    raise Unsupported(f"'{engine}' takes one feature per call")
                fc = fc["features"][0]
            values[engine] = fc
    values.update(args)
    ordered = [[k, values[k]] for k in order if k in values and k != "options"]
    request = {"fn": impl["call"]["name"].split(".", 1)[1], "args": ordered}
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "run.js"
        script.write_text(TURF_SCRIPT)
        r = subprocess.run([node, str(script), str(Path(modules) / "@turf" / "turf")], input=json.dumps(request),
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{request['fn']} failed: {r.stderr.strip()[-300:]}")
        data = json.loads(r.stdout)
        if isinstance(data, (int, float)):  # turf.area, turf.length
            return [float(data)]
        out = gpd.GeoDataFrame.from_features(data["features"], crs=4326).to_crs(CRS)
        return out if tabular(case) else [g for g in out.geometry if g is not None]


def write_dem(path: Path, part: str = RASTER) -> None:
    """The DEM, or its western or eastern half (for mosaics)."""
    from osgeo import gdal, osr
    import numpy as np
    gdal.UseExceptions()
    c0, c1 = {RASTER: (0, DEM_SIZE), RASTER_WEST: (0, DEM_SIZE // 2), RASTER_EAST: (DEM_SIZE // 2, DEM_SIZE)}[part]
    ds = gdal.GetDriverByName("GTiff").Create(str(path), c1 - c0, DEM_SIZE, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((DEM_ORIGIN[0] + c0 * DEM_CELL, DEM_CELL, 0, DEM_ORIGIN[1], 0, -DEM_CELL))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(SRID)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(DEM_NODATA)
    band.WriteArray(np.array([row[c0:c1] for row in dem_values()], dtype="float32"))
    ds = None


def read_raster(path: Path) -> list[float]:
    """Valid cell values of band 1."""
    from osgeo import gdal
    gdal.UseExceptions()
    ds = gdal.Open(str(path))
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray().astype(float).ravel()
    nodata = band.GetNoDataValue()
    return [float(v) for v in arr if not math.isnan(v) and (nodata is None or v != nodata)]


def run_gdal(gdal: str, impl: dict, op: dict, case: Case):
    ports, args = translate(impl, op, case)
    raster_out = op["outputs"][0]["type"] == "raster"
    with tempfile.TemporaryDirectory() as tmp:
        argv = [gdal, *impl["call"]["name"].split()[1:]]
        out = Path(tmp) / ("out.tif" if raster_out else "out.gpkg")
        for port, engine in ports.items():
            if port in case.inputs:
                data = case.inputs[port]
                parts = data if is_many(data) else [data]
                for i, d in enumerate(parts):
                    argv += [f"--{engine}", write_input(Path(tmp) / f"{port}{i}", d, case, port, ".gpkg")]
            elif engine and port in [p["name"] for p in op["outputs"]]:
                argv += [f"--{engine}", str(out)]
        for k, v in args.items():
            if isinstance(v, bool):
                if v:
                    argv.append(f"--{k}")
            elif isinstance(v, list):
                argv += [f"--{k}", ",".join(str(x) for x in v)]
            else:
                argv += [f"--{k}", str(v)]
        if not any(a == "--output" for a in argv):
            argv += ["--output", str(out)]
        r = subprocess.run(argv, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{' '.join(argv[:3])} failed: {(r.stderr or r.stdout).strip()[:300]}")
        if raster_out:
            return read_raster(out)
        if tabular(case):
            return gpd.read_file(out)
        return [g for g in gpd.read_file(out).geometry if g is not None]


def run_postgis(psql: str, dsn: str, impl: dict, op: dict, case: Case) -> list:
    ports, args = translate(impl, op, case)
    fn = impl["call"]["name"]
    aggregate = any("(aggregate)" in s.get("returns", "") for s in impl.get("signatures") or [])

    def geom_values(port):
        return ", ".join(f"(ST_GeomFromText('{g.wkt}', {SRID}), {i})" for i, g in enumerate(case.inputs[port]))

    positional: dict[int, str] = {}
    named: list[str] = []

    def put(engine: str, sql: str):
        if engine.startswith("#"):
            positional[int(engine[1:])] = sql
        else:
            named.append(f"{engine} => {sql}")

    def lit(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, str) and v.upper().startswith("EPSG:"):
            return v.split(":")[1]
        return "'" + str(v).replace("'", "''") + "'"

    from_parts, where = [], []
    table = None
    for port, data in case.inputs.items():
        if isinstance(data, pd.DataFrame):
            cols = ", ".join(data.columns)
            rows = ", ".join("(" + ", ".join(repr(float(v)) for v in row) + ")" for row in data.itertuples(index=False))
            from_parts.append(f"(VALUES {rows}) AS t({cols})")
            table = "t"
        elif ports.get(port):
            from_parts.append(f"(VALUES {geom_values(port)}) AS {port}(g, i)")
            put(ports[port], f"{port}.g")
    for k, v in args.items():
        if isinstance(v, tuple) and v[0] == "values":
            put(k, f"{table}.{v[1]}")
        elif isinstance(v, str) and table and v in case.inputs[next(iter(case.inputs))].columns:
            put(k, f"{table}.{v}")
        else:
            put(k, lit(v))
    call_args = [positional[i] for i in sorted(positional)] + named
    expr = f"{fn}({', '.join(call_args)})"
    if any(s.get("returns", "").startswith("SETOF") and s.get("returns") != "SETOF geometry"
           for s in impl.get("signatures") or []):
        expr = f"({expr}).geom"  # ST_Dump, ST_SquareGrid: rows of (..., geom, ...)
    value = case.measure.startswith("value:")
    group = ""
    if aggregate and "by" in case.params:
        port = next(iter(case.inputs))
        from_parts[0] = (f"(VALUES " + ", ".join(
            f"(ST_GeomFromText('{g.wkt}', {SRID}), '{k}')" for g, k in zip(case.inputs[port], case.attrs[port]["k"]))
            + f") AS {port}(g, k)")
        group = f" GROUP BY {port}.k"
    if len(ports) >= 2 and all(isinstance(case.inputs.get(p), list) for p in ports if p in case.inputs):
        names = [p for p in ports if p in case.inputs]
        if len(names) == 2:
            where.append(f"ST_Intersects({names[0]}.g, {names[1]}.g)")
    sql = f"SELECT {expr + '::float8' if value else f'ST_AsText({expr})'} FROM {', '.join(from_parts)}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += group
    r = subprocess.run([psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", dsn, "-c", sql],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{fn} failed: {r.stderr.strip()[:300]}")
    if value:
        return [float(line) for line in r.stdout.splitlines() if line.strip()]
    return [wkt.loads(line) for line in r.stdout.splitlines() if line.strip() and "EMPTY" not in line]


def dem_sql() -> str:
    rows = ",".join("[" + ",".join(repr(v) for v in row) + "]" for row in dem_values())
    return (f"ST_SetValues(ST_AddBand(ST_MakeEmptyRaster({DEM_SIZE}, {DEM_SIZE}, {DEM_ORIGIN[0]}, {DEM_ORIGIN[1]}, "
            f"{DEM_CELL}, {-DEM_CELL}, 0, 0, {SRID}), '32BF'::text, 0, {DEM_NODATA}), 1, 1, 1, ARRAY[{rows}]::double precision[][])")


def run_postgis_raster(psql: str, dsn: str, impl: dict, op: dict, case: Case):
    ports, args = translate(impl, op, case)
    fn = impl["call"]["name"]
    call = []
    for port, engine in ports.items():
        data = case.inputs.get(port)
        if data is None or engine is None:
            continue
        if is_many(data):
            raise Unsupported("this runner passes one raster; an aggregate over rows is not run here")
        if isinstance(data, str) and data == RASTER:
            call.append(f"{engine} => {dem_sql()}")
        else:
            union = " , ".join(f"ST_GeomFromText('{g.wkt}', {SRID})" for g in data)
            call.append(f"{engine} => ST_Union(ARRAY[{union}])")
    for k, v in args.items():
        if isinstance(v, bool):
            val = "true" if v else "false"
        elif isinstance(v, (int, float)):
            val = repr(v)
        elif isinstance(v, str) and v.upper().startswith("EPSG:"):
            val = v.split(":")[1]
        else:
            val = "'" + str(v).replace("'", "''") + "'"
        call.append(f"{k} => {val}")
    vector_out = op["outputs"][0]["type"] == "vector"
    if vector_out:  # ST_DumpAsPolygons and the like: one (geom, val) row per polygon
        sql = f"SELECT ST_AsText(({fn}({', '.join(call)})).geom)"
    else:
        sql = (f"SELECT v FROM (SELECT unnest((ST_DumpValues({fn}({', '.join(call)}), 1, true))) AS v) t "
               f"WHERE v IS NOT NULL")
    r = subprocess.run([psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", dsn, "-c", sql],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{fn} failed: {r.stderr.strip()[:300]}")
    if vector_out:
        return [wkt.loads(line) for line in r.stdout.splitlines() if line.strip()]
    return [float(x) for x in r.stdout.split()]


# ------------------------------------------------------------------ measures

def measure(kind: str, geoms) -> float:
    if kind == "raster_median":
        # Edge cells have incomplete neighbourhoods and engines treat them
        # differently (a documented difference); the median is the interior.
        return statistics.median(geoms) if geoms else float("nan")
    if kind == "raster_mean":
        return sum(geoms) / len(geoms) if geoms else float("nan")
    if kind == "raster_count":
        return float(len(geoms))
    if kind.startswith("value:"):
        name = kind.split(":", 1)[1]
        if isinstance(geoms, pd.DataFrame):
            cols = [c for c in geoms.columns if c.lower() == name or c.lower().endswith(name)]
            if not cols:
                cols = [c for c in geoms.columns if c != "geometry" and pd.api.types.is_numeric_dtype(geoms[c])][-1:]
            return float(pd.to_numeric(geoms[cols[0]]).sum())
        return float(sum(geoms))
    if kind.startswith("field_"):
        name = kind[len("field_"):]
        cols = [c for c in geoms.columns if c == name or c.lower().endswith(name)]
        if not cols:  # engines that name the column themselves (zonal_average, a layer's name)
            cols = [c for c in geoms.columns if c != "geometry" and pd.api.types.is_numeric_dtype(geoms[c])][-1:]
        return float(geoms[cols[0]].iloc[0])
    if kind == "area":
        return sum(g.area for g in geoms)
    if kind == "length":
        return sum(g.length for g in geoms)
    if kind == "count":
        return float(len(geoms))
    if kind == "coords":
        return float(sum(c for g in geoms for xy in shapely.get_coordinates(g) for c in xy))
    raise ValueError(kind)


def close(a: float, b: float, rel: float) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=1e-9)


# ---------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dist", type=Path)
    ap.add_argument("--gdal", default=shutil.which("gdal"))
    ap.add_argument("--psql", default=shutil.which("psql"))
    ap.add_argument("--dsn", default=None, help="PostGIS connection string (needs the postgis extension)")
    ap.add_argument("--qgis-process", default=shutil.which("qgis_process"))
    ap.add_argument("--wbt", default=shutil.which("whitebox_tools"))
    ap.add_argument("--rscript", default=shutil.which("Rscript"), help="Rscript with the sf and terra packages")
    ap.add_argument("--grass", default=shutil.which("grass"), help="the grass launcher")
    ap.add_argument("--turf", default=None, help="a node_modules folder with @turf/turf (run with node)")
    args = ap.parse_args()

    db = sqlite3.connect(f"file:{args.dist / 'registry.sqlite'}?mode=ro", uri=True)
    ops = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, entry FROM operations")}
    impls = [json.loads(r[0]) for r in db.execute("SELECT entry FROM implementations WHERE implements IS NOT NULL ORDER BY id")]

    def runner(impl):
        iface, software = impl["call"]["interface"], impl["software"]
        if iface == "python" and software in ("shapely", "geopandas"):
            return lambda op, case: run_python(impl, op, case)
        if iface == "python" and software in PYLIB_SOFTWARE and importlib.util.find_spec(
                {"xarray-spatial": "xrspatial", "dask-geopandas": "dask_geopandas"}.get(software, software)):
            return lambda op, case: run_pylib(impl, op, case)
        if iface == "js" and software == "turf-js" and args.turf and shutil.which("node"):
            return lambda op, case: run_turf(shutil.which("node"), args.turf, impl, op, case)
        if iface == "cli" and software == "grass" and args.grass:
            return lambda op, case: run_grass(args.grass, impl, op, case)
        if iface == "r" and software in ("sf", "terra") and args.rscript:
            return lambda op, case: run_r(args.rscript, impl, op, case)
        if iface == "cli" and software == "gdal" and args.gdal:
            return lambda op, case: run_gdal(args.gdal, impl, op, case)
        if iface == "sql" and software == "postgis" and args.psql and args.dsn:
            return lambda op, case: run_postgis(args.psql, args.dsn, impl, op, case)
        if iface == "qgis-process" and args.qgis_process:
            return lambda op, case: run_qgis(args.qgis_process, impl, op, case)
        if iface == "cli" and software == "whiteboxtools" and args.wbt:
            return lambda op, case: run_whitebox(args.wbt, impl, op, case)
        if iface == "sql" and software == "postgis-raster" and args.psql and args.dsn:
            return lambda op, case: run_postgis_raster(args.psql, args.dsn, impl, op, case)
        return None

    failed = 0
    rows = []
    for case in CASES + RASTER_CASES:
        op = ops[case.operation]
        results = []
        for impl in impls:
            if impl.get("implements") != case.operation:
                continue
            run = runner(impl)
            if run is None:
                rows.append((case, impl["id"], "skipped", "engine not available here"))
                continue
            try:
                value = measure(case.measure, run(op, case))
                if impl["id"] in OUTPUT_SCALE and case.measure.startswith("raster_"):
                    value *= OUTPUT_SCALE[impl["id"]][0]
                results.append((impl["id"], value))
            except Unsupported as e:
                rows.append((case, impl["id"], "skipped", str(e)))
            except Exception as e:  # noqa: BLE001 - any engine error is a failure to report
                rows.append((case, impl["id"], "FAIL", f"{type(e).__name__}: {e}"[:300]))
                failed += 1
        if any(math.isnan(v) for _, v in results):
            for impl_id, v in [r for r in results if math.isnan(r[1])]:
                rows.append((case, impl_id, "FAIL", "no valid values in the output"))
                failed += 1
            results = [r for r in results if not math.isnan(r[1])]
        reference = case.expected if case.expected is not None else (results[0][1] if results else None)
        for impl_id, value in results:
            ok = close(value, reference, case.tolerance)
            known = KNOWN_DIFFERENCES.get((impl_id, case.title))
            if not ok and not known:
                failed += 1
            status = "ok" if ok else ("differs" if known else "FAIL")
            rows.append((case, impl_id, status, f"{case.measure} {value:.6g}" + (
                "" if ok else f" ({value:.12g}), expected {reference:.12g}" + (f": {known}" if known else ""))))
    for case, impl_id, status, detail in rows:
        print(f"{status:8} {case.operation:16} {impl_id:40} {case.title}: {detail}")
    ran = sum(1 for r in rows if r[2] in ("ok", "FAIL", "differs"))
    differs = sum(1 for r in rows if r[2] == "differs")
    print(f"\n{ran} runs, {failed} failed, {differs} known differences, "
          f"{sum(1 for r in rows if r[2] == 'skipped')} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
