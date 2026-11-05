#!/usr/bin/env python3
"""Run each mapped implementation on the same small input and check the results agree.

    python checks/equivalence.py DIST [--gdal PATH] [--psql PATH --dsn CONNINFO]

DIST is a built registry (registry.sqlite). For every case below, each
implementation mapped to the case's operation is called through its
crosswalk, exactly as Columbus would translate the canonical parameters,
and a measure of the result (area, length, count, coordinates) is compared
with the expected value or, where there is no closed form, with the other
engines' results. A wrong crosswalk (a parameter mapped to the wrong
argument, a unit or value translated wrongly) shows up as a failure; an
engine that cannot honour a canonical value (`unsupported`, `fixed`) is
reported as skipped with the reason, which is the documented difference.

Engines not available on this machine are skipped. Needs geopandas and
shapely in the running Python; GDAL through --gdal; PostGIS through --psql.
Exit status: 0 when nothing failed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import importlib
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


@dataclass
class Case:
    operation: str
    title: str
    inputs: dict[str, Any]          # port -> list of geometries, or a DataFrame for tables
    params: dict[str, Any]          # canonical parameters
    measure: str                    # area | length | count | coords
    expected: float | None = None   # None: compare engines with each other
    tolerance: float = 1e-6         # relative
    attrs: dict[str, list] = field(default_factory=dict)  # extra columns per port


CASES = [
    Case("buffer", "100 m square buffered by 10 m", {"layer": [poly(0, 0, 100, 100)]},
         {"distance": 10, "unit": "m", "segments": 8}, "area",
         expected=100 * 100 + 4 * 100 * 10 + math.pi * 10 ** 2, tolerance=0.005),
    Case("buffer", "buffer dissolved into one shape", {"layer": [poly(0, 0, 10, 10), poly(15, 0, 25, 10)]},
         {"distance": 5, "unit": "m", "dissolve": True}, "count", expected=1),
    Case("reproject", "a point to EPSG:3081", {"layer": [shapely.Point(621000, 3349000)]},
         {"crs": "EPSG:3081"}, "coords", tolerance=1e-9),
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
]


# Documented output differences the tests convert before comparing, so they still
# check the substance: implementation id -> (factor, what it means).
OUTPUT_SCALE = {
    "whiteboxtools-hillshade": (255 / 32767, "output is 0 to 32767, compared as 0 to 255"),
}


class Unsupported(Exception):
    """The implementation cannot honour this case's canonical values (a documented difference)."""


# ---------------------------------------------------------------- translation

def translate(impl: dict, op: dict, case: Case) -> tuple[dict, dict]:
    """Canonical ports and parameters -> engine arguments, through the crosswalk.
    Returns (ports: canonical port -> engine name or None for `self`, args: engine name -> value)."""
    cw = impl.get("crosswalk") or {}
    defaults = {k: v.get("default") for k, v in (op.get("parameters") or {}).items()}
    ports: dict[str, str | None] = {}
    method = impl["call"]["interface"] == "python" and any(c in impl["call"]["name"] for c in (".GeoSeries.", ".GeoDataFrame."))
    first_input = op["inputs"][0]["name"]
    eparams = impl.get("parameters") or {}
    for port in [p["name"] for p in op["inputs"] + op["outputs"]]:
        item = cw.get(port)
        if isinstance(item, dict) and "param" in item:
            item = item["param"]
        if isinstance(item, str):
            etype = str((eparams.get(item) or {}).get("type", "")).lower()
            data = case.inputs.get(port)
            if isinstance(data, list) and "raster" in etype and "vector" not in etype:
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
            if fixed == value or (fixed == "crs-units" and value == "m"):
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
        result = getattr(self_obj, parts[-1])(**kwargs)
    else:
        mod = importlib.import_module(parts[0])
        result = getattr(mod, parts[-1])(**kwargs)
    return geometries(result)


def geometries(result) -> list:
    if isinstance(result, gpd.GeoDataFrame):
        return [g for g in result.geometry if g is not None]
    if isinstance(result, (gpd.GeoSeries, gpd.array.GeometryArray)):
        return [g for g in result if g is not None]
    if isinstance(result, shapely.Geometry):
        return [result]
    return [g for g in list(result) if g is not None]


def stage_inputs(tmp: str, ports: dict, op: dict, case: Case, vector_ext: str) -> dict[str, str]:
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
        if isinstance(data, str) and data == RASTER:
            path = Path(tmp) / f"{port}.tif"
            write_dem(path)
        elif isinstance(data, pd.DataFrame):
            path = Path(tmp) / f"{port}.csv"
            data.to_csv(path, index=False)
        else:
            path = Path(tmp) / f"{port}{vector_ext}"
            gpd.GeoDataFrame(case.attrs.get(port, {}), geometry=list(data), crs=CRS).to_file(path)
        paths[port] = str(path)
    return paths


def read_output(path: str, op: dict, case: Case):
    if op["outputs"][0]["type"] == "raster":
        return read_raster(Path(path))
    if case.measure.startswith("field_"):
        return gpd.read_file(path)
    return [g for g in gpd.read_file(path).geometry if g is not None]


def run_qgis(qp: str, impl: dict, op: dict, case: Case):
    ports, args = translate(impl, op, case)
    with tempfile.TemporaryDirectory() as tmp:
        paths = stage_inputs(tmp, ports, op, case, ".gpkg")
        argv = [qp, "run", impl["call"]["name"], "--"]
        for port, path in paths.items():
            argv.append(f"{ports[port]}={path}")
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
            argv.append(f"--{ports[port]}={path}")
        for k, v in args.items():
            if isinstance(v, bool):
                if v:
                    argv.append(f"--{k}")
            else:
                argv.append(f"--{k}={v}")
        r = subprocess.run(argv, capture_output=True, text=True)
        out = next((paths[p["name"]] for p in op["outputs"] if p["name"] in paths), None)
        if r.returncode != 0 or not out or not Path(out).exists():
            raise RuntimeError(f"whitebox {impl['call']['name']} failed: {(r.stderr or r.stdout).strip()[-300:]}")
        return read_output(out, op, case)


def write_dem(path: Path) -> None:
    from osgeo import gdal, osr
    import numpy as np
    gdal.UseExceptions()
    ds = gdal.GetDriverByName("GTiff").Create(str(path), DEM_SIZE, DEM_SIZE, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((DEM_ORIGIN[0], DEM_CELL, 0, DEM_ORIGIN[1], 0, -DEM_CELL))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(SRID)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(DEM_NODATA)
    band.WriteArray(np.array(dem_values(), dtype="float32"))
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
                if isinstance(data, str) and data == RASTER:
                    path = Path(tmp) / f"{port}.tif"
                    write_dem(path)
                elif isinstance(data, pd.DataFrame):
                    path = Path(tmp) / f"{port}.csv"
                    data.to_csv(path, index=False)
                else:
                    path = Path(tmp) / f"{port}.gpkg"
                    gpd.GeoDataFrame(case.attrs.get(port, {}), geometry=list(data), crs=CRS).to_file(path)
                argv += [f"--{engine}", str(path)]
            elif engine and port in [p["name"] for p in op["outputs"]]:
                argv += [f"--{engine}", str(out)]
        for k, v in args.items():
            if isinstance(v, bool):
                if v:
                    argv.append(f"--{k}")
            else:
                argv += [f"--{k}", str(v)]
        if not any(a == "--output" for a in argv):
            argv += ["--output", str(out)]
        r = subprocess.run(argv, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{' '.join(argv[:3])} failed: {(r.stderr or r.stdout).strip()[:300]}")
        if raster_out:
            return read_raster(out)
        if case.measure.startswith("field_"):
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
    sql = f"SELECT ST_AsText({expr}) FROM {', '.join(from_parts)}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += group
    r = subprocess.run([psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", dsn, "-c", sql],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{fn} failed: {r.stderr.strip()[:300]}")
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
    sql = (f"SELECT v FROM (SELECT unnest((ST_DumpValues({fn}({', '.join(call)}), 1, true))) AS v) t "
           f"WHERE v IS NOT NULL")
    r = subprocess.run([psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", dsn, "-c", sql],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{fn} failed: {r.stderr.strip()[:300]}")
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
    if kind.startswith("field_"):
        name = kind[len("field_"):]
        col = name if name in geoms.columns else next(c for c in geoms.columns if c.lower().endswith(name))
        return float(geoms[col].iloc[0])
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
    args = ap.parse_args()

    db = sqlite3.connect(f"file:{args.dist / 'registry.sqlite'}?mode=ro", uri=True)
    ops = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, entry FROM operations")}
    impls = [json.loads(r[0]) for r in db.execute("SELECT entry FROM implementations WHERE implements IS NOT NULL ORDER BY id")]

    def runner(impl):
        iface, software = impl["call"]["interface"], impl["software"]
        if iface == "python" and software in ("shapely", "geopandas"):
            return lambda op, case: run_python(impl, op, case)
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
            if not ok:
                failed += 1
            rows.append((case, impl_id, "ok" if ok else "FAIL",
                         f"{case.measure} {value:.6g}" + ("" if ok else f", expected {reference:.6g}")))
    for case, impl_id, status, detail in rows:
        print(f"{status:8} {case.operation:16} {impl_id:40} {case.title}: {detail}")
    ran = sum(1 for r in rows if r[2] in ("ok", "FAIL"))
    print(f"\n{ran} runs, {failed} failed, {sum(1 for r in rows if r[2] == 'skipped')} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
