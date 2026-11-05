#!/usr/bin/env python3
"""Harvest Turf.js functions from its TypeScript declarations.

    npm install --ignore-scripts --prefix DIR @turf/turf typescript@5
    python harvest/turf.py --node-modules DIR/node_modules

turf_declarations.mjs reads every @turf/* package's index.d.ts with TypeScript's
parser (Turf itself is never run). One implementation per exported function, called
as turf.<name>; overloads go under `signatures`; the fields of an `options` object
become parameters named options.<field>, since that is how Turf takes most settings.
Writes implementations/turf-js/.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOFTWARE = "turf-js"
HERE = Path(__file__).resolve().parent


def harvest(node: str, node_modules: Path) -> tuple[str, list[dict]]:
    out = subprocess.run([node, str(HERE / "turf_declarations.mjs"), str(node_modules)],
                         capture_output=True, text=True, check=True).stdout
    functions = json.loads(out)
    version = json.loads((node_modules / "@turf" / "turf" / "package.json").read_text())["version"]
    entries, seen = [], set()
    for f in sorted(functions, key=lambda f: (f["name"], f["package"])):
        eid = common.slug("turf", f["name"])
        if eid in seen:  # the same function re-declared by another package
            continue
        seen.add(eid)
        params: dict[str, dict] = {}
        signatures = []
        for o in f["overloads"]:
            args = []
            for p in o["params"]:
                args.append({"name": p["name"], "type": p["type"][:200]})
                params.setdefault(p["name"], common.param(p["type"][:200], required=not p["optional"]))
                for fld in p.get("fields") or []:
                    params.setdefault(f"{p['name']}.{fld['name']}",
                                      common.param(fld["type"][:200], note=f"field of {p['name']}"))
            signatures.append({"arguments": args, "returns": o["returns"][:200]})
        entries.append(common.entry(
            id=eid, name=f"turf.{f['name']}", software=SOFTWARE, interface="js", call_name=f"turf.{f['name']}",
            harvester="turf", engine_version=version, parameters=params,
            signatures=signatures if len(signatures) > 1 else None,
            notes=f"From {f['package']}."))
    return version, entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--node", default="node")
    ap.add_argument("--node-modules", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    ver, entries = harvest(args.node, args.node_modules)
    common.report(SOFTWARE, ver, common.write(SOFTWARE, entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
