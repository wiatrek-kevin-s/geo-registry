#!/usr/bin/env python3
"""Harvest Shapely and GeoPandas from the installed packages, by introspection.

    python harvest/python_libs.py

Run it with the Python that has the versions to describe. Writes
implementations/shapely/ (the public functions in the `shapely` namespace) and
implementations/geopandas/ (the public functions in the `geopandas` namespace,
GeoSeries methods and properties, and the GeoDataFrame methods GeoSeries does
not have). Only what GeoPandas defines itself is included, not what it
inherits from pandas. Types come from defaults where Python gives no annotation.
"""

from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def kind_of(default) -> str:
    if isinstance(default, bool):
        return "boolean"
    if isinstance(default, int):
        return "integer"
    if isinstance(default, float):
        return "number"
    if isinstance(default, str):
        return "string"
    return "any"


def parameters(fn, skip_self: bool) -> dict:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return {}
    out = {}
    for i, (name, p) in enumerate(sig.parameters.items()):
        if skip_self and i == 0:
            continue
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        has_default = p.default is not p.empty
        ann = p.annotation
        type_ = ann if isinstance(ann, str) else (getattr(ann, "__name__", None) if ann is not p.empty else None)
        out[name] = common.param(type_ or (kind_of(p.default) if has_default else "any"),
                                 required=not has_default,
                                 default=p.default if has_default else None)
    return out


def own_members(cls, module_prefix: str, exclude: set[str] = frozenset()):
    """Public functions and properties `cls` gets from classes in `module_prefix`."""
    seen = {}
    for klass in reversed(cls.__mro__):
        if not klass.__module__.startswith(module_prefix):
            continue
        for name, v in vars(klass).items():
            if name.startswith("_") or name in exclude:
                continue
            if isinstance(v, (staticmethod, classmethod)):
                v = v.__func__
            if inspect.isfunction(v) or isinstance(v, property):
                seen[name] = v
    return dict(sorted(seen.items()))


def harvest_shapely():
    import shapely
    ver = shapely.__version__
    entries = []
    for name in sorted(dir(shapely)):
        fn = getattr(shapely, name)
        if name.startswith("_") or not inspect.isfunction(fn) or not fn.__module__.startswith("shapely"):
            continue
        entries.append(common.entry(
            id=common.slug("shapely", name), name=f"shapely.{name}", software="shapely",
            interface="python", call_name=f"shapely.{name}", harvester="python-libs",
            engine_version=ver, parameters=parameters(fn, skip_self=False)))
    return ver, entries


def harvest_geopandas():
    import geopandas
    ver = geopandas.__version__
    entries = []
    for name in sorted(dir(geopandas)):
        fn = getattr(geopandas, name)
        if name.startswith("_") or not inspect.isfunction(fn) or not fn.__module__.startswith("geopandas"):
            continue
        entries.append(common.entry(
            id=common.slug("geopandas", name), name=f"geopandas.{name}", software="geopandas",
            interface="python", call_name=f"geopandas.{name}", harvester="python-libs",
            engine_version=ver, parameters=parameters(fn, skip_self=False)))
    series = own_members(geopandas.GeoSeries, "geopandas")
    frame = own_members(geopandas.GeoDataFrame, "geopandas", exclude=set(series))
    for cls, members in (("GeoSeries", series), ("GeoDataFrame", frame)):
        for name, v in members.items():
            is_prop = isinstance(v, property)
            entries.append(common.entry(
                id=common.slug("geopandas", cls, name), name=f"{cls}.{name}", software="geopandas",
                interface="python", call_name=f"geopandas.{cls}.{name}", harvester="python-libs",
                engine_version=ver,
                parameters={} if is_prop else parameters(v, skip_self=True),
                notes="Property." if is_prop else None))
    return ver, entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    for software, fn in (("shapely", harvest_shapely), ("geopandas", harvest_geopandas)):
        ver, entries = fn()
        common.report(software, ver, common.write(software, entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
