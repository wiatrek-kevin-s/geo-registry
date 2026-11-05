#!/usr/bin/env python3
"""Harvest QGIS Processing algorithms from `qgis_process --json list` and `--json help`.

    python harvest/qgis.py [--qgis-process PATH] [--jobs 4]

Writes implementations/qgis/qgis-<provider>-<algorithm>.yaml, one per algorithm of
every provider QGIS loads (native, qgis, gdal, pdal, 3d, ...), called as
`qgis_process run <provider>:<algorithm>`. Runs headless (QT_QPA_PLATFORM=offscreen).
Enumerations keep QGIS's option numbers as values, with the option names in the note.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ENV = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}


def run(qp: str, *args: str) -> dict:
    out = subprocess.run([qp, "--json", *args], capture_output=True, text=True, check=True, env=ENV).stdout
    return json.loads(out[out.index("{"):])


def parameters(help_json: dict) -> dict:
    out = {}
    for name, p in (help_json.get("parameters") or {}).items():
        t = p.get("type")
        type_ = (t.get("id") if isinstance(t, dict) else t) \
            or (p.get("raw_definition") or {}).get("parameter_type") or "any"
        notes = []
        if p.get("is_destination"):
            notes.append("output")
        values = None
        options = p.get("available_options")
        if isinstance(options, dict) and options:
            values = [int(k) if str(k).isdigit() else k for k in options]
            notes.append(", ".join(f"{k} {v}" for k, v in options.items()))
        if (p.get("raw_definition") or {}).get("allow_multiple"):
            notes.append("multiple values")
        out[name] = common.param(type_, required=not p.get("optional", True), default=p.get("default_value"),
                                 values=values, note="; ".join(notes) or None)
    return out


def harvest(qp: str, jobs: int) -> tuple[str, list[dict]]:
    listing = run(qp, "list")
    ver = re.match(r"[\d.]+", run(qp, "help", "native:buffer").get("qgis_version", "")).group(0)
    algs = [(alg_id, meta) for prov in listing["providers"].values()
            for alg_id, meta in prov.get("algorithms", {}).items()]

    def one(item):
        alg_id, meta = item
        try:
            params = parameters(run(qp, "help", alg_id))
        except Exception as e:  # noqa: BLE001 - one odd algorithm must not stop the harvest
            print(f"  could not describe {alg_id}: {e}", file=sys.stderr)
            return None
        provider, name = alg_id.split(":", 1)
        notes = "Deprecated in QGIS." if meta.get("deprecated") else None
        return common.entry(
            id=common.slug("qgis", provider, name), name=alg_id, software="qgis", interface="qgis-process",
            call_name=alg_id, harvester="qgis", engine_version=ver, parameters=params,
            docs=meta.get("help_url") or None, notes=notes)

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        entries = [e for e in pool.map(one, sorted(algs)) if e]
    return ver, entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--qgis-process", default="qgis_process", help="the qgis_process program")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    ver, entries = harvest(args.qgis_process, args.jobs)
    common.report("qgis", ver, common.write("qgis", entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
