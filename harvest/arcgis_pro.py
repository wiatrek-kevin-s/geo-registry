#!/usr/bin/env python3
"""Turn an ArcGIS Pro tool export into implementation entries.

    python harvest/arcgis_pro.py arcgis-pro-tools.jsonl

The export comes from harvest/arcgis_pro_export.py, run in ArcGIS Pro's Python on a
machine with Pro (this machine needs neither Pro nor arcpy). Writes
implementations/arcgis-pro/arcgis-pro-<toolbox alias>-<tool>.yaml, one per tool,
called as arcpy.<alias>.<Tool>. Tools the export could not describe are skipped
and listed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def parameters(params: list[dict]) -> dict:
    out = {}
    for p in params:
        notes = []
        if (p.get("direction") or "").lower() == "output":
            notes.append("output")
        if (p.get("parameterType") or "").lower() == "derived":
            notes.append("derived (set by the tool)")
        if p.get("multiValue"):
            notes.append("multiple values")
        out[p["name"]] = common.param(
            p.get("datatype") or "any",
            required=(p.get("parameterType") or "").lower() == "required",
            default=p.get("default"),
            values=p.get("values"),
            note="; ".join(notes) or None)
    return out


def convert(path: Path) -> tuple[str, list[dict], list[str]]:
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines or "version" not in lines[0]:
        raise SystemExit(f"{path}: not an export from arcgis_pro_export.py")
    version = lines[0]["version"]
    entries, skipped = [], []
    for rec in lines[1:]:
        call = f"arcpy.{rec['alias']}.{rec['tool']}"
        if "error" in rec:
            skipped.append(f"{call}: {rec['error']}")
            continue
        entries.append(common.entry(
            id=common.slug("arcgis-pro", rec["alias"], rec["tool"]), name=call, software="arcgis-pro",
            interface="python", call_name=call, harvester="arcgis-pro", engine_version=version,
            parameters=parameters(rec.get("params") or []),
            notes=f"In {rec['toolbox']}."))
    return version, entries, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("export", type=Path)
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    version, entries, skipped = convert(args.export)
    common.report("arcgis-pro", version, common.write("arcgis-pro", entries, args.out))
    for s in skipped:
        print(f"  skipped {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
