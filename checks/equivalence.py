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
    for port in [p["name"] for p in op["inputs"] + op["outputs"]]:
        item = cw.get(port)
        if isinstance(item, str):
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
            if fixed == value or (fixed == "crs-units" and name == "unit" and value == "m"):
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


def run_gdal(gdal: str, impl: dict, op: dict, case: Case) -> list:
    ports, args = translate(impl, op, case)
    with tempfile.TemporaryDirectory() as tmp:
        argv = [gdal, *impl["call"]["name"].split()[1:]]
        out = Path(tmp) / "out.gpkg"
        for port, engine in ports.items():
            if port in case.inputs:
                data = case.inputs[port]
                if isinstance(data, pd.DataFrame):
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


# ------------------------------------------------------------------ measures

def measure(kind: str, geoms: list) -> float:
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
        return None

    failed = 0
    rows = []
    for case in CASES:
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
                results.append((impl["id"], value))
            except Unsupported as e:
                rows.append((case, impl["id"], "skipped", str(e)))
            except Exception as e:  # noqa: BLE001 - any engine error is a failure to report
                rows.append((case, impl["id"], "FAIL", f"{type(e).__name__}: {e}"[:300]))
                failed += 1
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
