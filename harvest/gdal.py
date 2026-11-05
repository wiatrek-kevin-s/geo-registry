#!/usr/bin/env python3
"""Harvest GDAL's command-line algorithms from `gdal --json-usage` (GDAL 3.11 and later).

    python harvest/gdal.py [--gdal PATH]

Writes implementations/gdal/gdal-<group>-<command>.yaml, one per command that
does the work (not the groups such as `gdal vector`). Arguments in GDAL's
"Common" category (help, progress, quiet and the like) are left out.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

DIRECTION = {"input_arguments": None, "output_arguments": "output", "input_output_arguments": "input and output"}


def version(gdal: str) -> str:
    out = subprocess.run([gdal, "--version"], capture_output=True, text=True, check=True).stdout
    m = re.search(r"GDAL (\d+\.\d+\.\d+)", out)
    if not m:
        raise SystemExit(f"cannot read the GDAL version from {out!r}")
    return m.group(1)


def leaves(node: dict):
    subs = node.get("sub_algorithms") or []
    if not subs:
        yield node
    for s in subs:
        yield from leaves(s)


def parameters(alg: dict) -> dict:
    params = {}
    for key, direction in DIRECTION.items():
        for a in alg.get(key) or []:
            if a.get("category") == "Common":
                continue
            notes = []
            if direction:
                notes.append(direction)
            if a.get("dataset_type"):
                notes.append(" or ".join(a["dataset_type"]) + " dataset")
            lo, hi = a.get("min_value"), a.get("max_value")
            if lo is not None and hi is not None:
                notes.append(f"from {lo} to {hi}")
            elif lo is not None:
                notes.append(f"at least {lo}" if a.get("min_value_is_included", True) else f"more than {lo}")
            elif hi is not None:
                notes.append(f"at most {hi}" if a.get("max_value_is_included", True) else f"less than {hi}")
            if a.get("mutual_exclusion_group"):
                notes.append(f"exclusive group {a['mutual_exclusion_group']}")
            params[a["name"]] = common.param(
                a["type"], required=bool(a.get("required")), default=a.get("default"),
                values=a.get("choices"), note="; ".join(notes) or None)
    return params


def harvest(gdal: str) -> tuple[str, list[dict]]:
    ver = version(gdal)
    usage = json.loads(subprocess.run([gdal, "--json-usage"], capture_output=True, text=True, check=True).stdout)
    entries = []
    for alg in leaves(usage):
        path = alg.get("full_path") or []
        if len(path) < 2:
            continue
        entries.append(common.entry(
            id=common.slug(*path), name=" ".join(path), software="gdal", interface="cli",
            call_name=" ".join(path), harvester="gdal", engine_version=ver,
            parameters=parameters(alg), docs=alg.get("url")))
    return ver, entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gdal", default="gdal", help="the gdal program (default: gdal on PATH)")
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    ver, entries = harvest(args.gdal)
    common.report("gdal", ver, common.write("gdal", entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
