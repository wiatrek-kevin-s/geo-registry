#!/usr/bin/env python3
"""Harvest Python GIS packages listed in harvest/python-packages.yml, by introspection.

    python harvest/python_packages.py [--only SOFTWARE ...]

Run it with a Python that has the packages installed (harvest/environment-python.yml).
For each package it walks the public modules (none whose name, or a parent's, starts
with an underscore, and no tests or vendored code), and records every public function
and class the package defines itself, once, under its shortest public path
(rasterio.warp.reproject). A class is called through its constructor, unless the
config lists it under `methods`, in which case each public method is a tool
(rioxarray's `.rio` accessor). Parameters come from Python's signatures; types from
annotations where present, else from defaults. Writes implementations/<software>/.
A package that cannot be imported is reported and left as it was.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import inspect
import pkgutil
import re
import sys
import warnings
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from python_libs import own_members, parameters  # noqa: E402

CONFIG = Path(__file__).resolve().parent / "python-packages.yml"
SKIP_PART = re.compile(r"^(_.*|tests?|testing|conftest|compat|externals|vendor(ed)?|examples?|benchmarks?|docs?)$")
# Back-end plumbing, not tools: GPU fallbacks (a stand-in `cupy` class when CuPy is
# missing), CUDA launch helpers, and checks for which array library is in use.
PLUMBING = re.compile(r"(^|_)(cupy|cuda|numba)(_|$)|^(is|has)_.*(dask|cupy|cuda)", re.IGNORECASE)


def version_of(mod, dist: str | None = None) -> str:
    v = getattr(mod, "__version__", None)
    if isinstance(v, str) and v:
        return v.lstrip("v")
    for name in filter(None, (dist, mod.__name__, mod.__name__.split(".")[0], mod.__name__.replace("_", "-"))):
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return "unknown"


def modules(root, include: list[str] | None, skip: list[str] | None = None):
    """The root module and every public submodule that imports (minus `skip` and below)."""
    found, skipped = [root], []
    if hasattr(root, "__path__"):
        for info in pkgutil.walk_packages(root.__path__, root.__name__ + ".", onerror=lambda n: skipped.append(n)):
            if any(SKIP_PART.match(p) for p in info.name.split(".")[1:]):
                continue
            if include and not any(info.name == i or info.name.startswith(i + ".") for i in include):
                continue
            if skip and any(info.name == s or info.name.startswith(s + ".") for s in skip):
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    found.append(importlib.import_module(info.name))
            except Exception as e:  # noqa: BLE001 - optional dependencies missing, etc.
                skipped.append(f"{info.name}: {type(e).__name__}")
    if include:
        found = [m for m in found if any(m.__name__ == i or m.__name__.startswith(i + ".") for i in include)]
    return found, skipped


def public_callables(mod, package: str, exclude: list[re.Pattern] = ()):
    names = getattr(mod, "__all__", None)
    if not isinstance(names, (list, tuple)):
        names = [n for n in vars(mod) if not n.startswith("_")]
    for name in names:
        if not isinstance(name, str) or name.startswith("_") or PLUMBING.search(name) or any(x.search(name) for x in exclude):
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # deprecated aliases warn when touched
            obj = getattr(mod, name, None)
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        if (getattr(obj, "__module__", "") or "").split(".")[0] != package:
            continue  # re-exported from another package
        if inspect.isclass(obj) and issubclass(obj, (BaseException, Warning)):
            continue
        yield name, obj


def harvest_package(cfg: dict) -> tuple[str, list[dict], list[str]]:
    software, modname = cfg["software"], cfg["module"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        root = importlib.import_module(modname)
    package = modname.split(".")[0]
    ver = version_of(root, cfg.get("dist"))
    mods, skipped = modules(root, cfg.get("include"), cfg.get("skip_modules"))
    best: dict[int, tuple[str, object]] = {}
    exclude = [re.compile(x) for x in cfg.get("exclude") or []]
    for mod in mods:
        for name, obj in public_callables(mod, package, exclude):
            path = f"{mod.__name__}.{name}"
            cur = best.get(id(obj))
            if cur is None or (path.count("."), path) < (cur[0].count("."), cur[0]):
                best[id(obj)] = (path, obj)
    method_classes = set(cfg.get("methods") or [])
    entries = []
    for path, obj in sorted(best.values(), key=lambda t: t[0]):
        is_class = inspect.isclass(obj)
        full = f"{obj.__module__}.{obj.__qualname__}" if is_class else None
        if is_class and (full in method_classes or path in method_classes):
            continue  # its methods are listed below instead
        entries.append(common.entry(
            id=common.slug(path), name=path, software=software, interface="python", call_name=path,
            harvester="python-packages", engine_version=ver,
            parameters=parameters(obj.__init__ if is_class else obj, skip_self=is_class),
            notes="Class: called through its constructor." if is_class else None))
    for cls_path in sorted(method_classes):
        mod_path, cls_name = cls_path.rsplit(".", 1)
        cls = getattr(importlib.import_module(mod_path), cls_name)
        for name, v in own_members(cls, package).items():
            is_prop = isinstance(v, property)
            call = f"{cls_path}.{name}"
            entries.append(common.entry(
                id=common.slug(cls_path, name), name=f"{cls_name}.{name}", software=software,
                interface="python", call_name=call, harvester="python-packages", engine_version=ver,
                parameters={} if is_prop else parameters(v, skip_self=True),
                notes="Property." if is_prop else None))
    # Two paths can slug to the same id (a_b and a.b): keep the first, report the rest.
    seen, unique = set(), []
    for e in entries:
        if e["id"] in seen:
            skipped.append(f"{e['name']}: same id as another tool")
            continue
        seen.add(e["id"])
        unique.append(e)
    return ver, unique, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--only", nargs="*", help="harvest only these software ids")
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    failed = 0
    for cfg in yaml.safe_load(args.config.read_text(encoding="utf-8"))["packages"]:
        if args.only and cfg["software"] not in args.only:
            continue
        try:
            ver, entries, skipped = harvest_package(cfg)
        except Exception as e:  # noqa: BLE001 - one package must not stop the others
            print(f"{cfg['software']}: cannot import {cfg['module']} ({type(e).__name__}: {e}); left as it was")
            failed += 1
            continue
        common.report(cfg["software"], ver, common.write(cfg["software"], entries, args.out))
        if skipped:
            print(f"  {len(skipped)} modules or names skipped (missing optional dependencies, duplicates)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
