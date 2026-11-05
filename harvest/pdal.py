#!/usr/bin/env python3
"""Harvest PDAL's pipeline stages from `pdal --drivers --showjson` and `pdal --options`.

    python harvest/pdal.py [--pdal PATH]

Writes implementations/pdal/pdal-<stage>.yaml, one per reader, filter and
writer. PDAL does not report option types, so each option's type is
`option`. The options every stage has (user_data, log, option_file) are left out.
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

GENERIC = {"user_data", "log", "option_file"}


def run(pdal: str, *args: str) -> str:
    return subprocess.run([pdal, *args], capture_output=True, text=True, check=True).stdout


def version(pdal: str) -> str:
    m = re.search(r"pdal (\d+\.\d+\.\d+)", run(pdal, "--version"))
    if not m:
        raise SystemExit("cannot read the PDAL version")
    return m.group(1)


def options(pdal: str, stage: str) -> dict:
    data = json.loads(run(pdal, "--options", stage, "--showjson"))
    # Shape: [stage name, [{name, default?, description}, ...]]
    opts = data[1] if isinstance(data, list) and len(data) == 2 else []
    params = {}
    for o in opts:
        name = o.get("name")
        if not name or name in GENERIC:
            continue
        default = o.get("default")
        params[name] = common.param("option", default=default if default not in ("", None) else None)
    return params


def harvest(pdal: str) -> tuple[str, list[dict]]:
    ver = version(pdal)
    drivers = json.loads(run(pdal, "--drivers", "--showjson"))
    entries = []
    for d in drivers:
        stage = d["name"]
        notes = "streamable" if d.get("streamable") else None
        entries.append(common.entry(
            id=common.slug("pdal", stage), name=stage, software="pdal", interface="pdal-pipeline",
            call_name=stage, harvester="pdal", engine_version=ver,
            parameters=options(pdal, stage), docs=d.get("link"), notes=notes))
    return ver, entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdal", default="pdal", help="the pdal program (default: pdal on PATH)")
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    ver, entries = harvest(args.pdal)
    common.report("pdal", ver, common.write("pdal", entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
