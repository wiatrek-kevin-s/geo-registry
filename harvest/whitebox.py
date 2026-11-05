#!/usr/bin/env python3
"""Harvest WhiteboxTools from `whitebox_tools --listtools` and `--toolparameters`.

    python harvest/whitebox.py [--wbt PATH]

Writes implementations/whiteboxtools/whiteboxtools-<tool>.yaml, one per tool,
called as `whitebox_tools --run=<Tool>`. Parameters are named by their long flag
(`--dem` becomes `dem`).
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


def run(wbt: str, *args: str) -> str:
    return subprocess.run([wbt, *args], capture_output=True, text=True, check=True).stdout


def version(wbt: str) -> str:
    m = re.search(r"v(\d+\.\d+\.\d+)", run(wbt, "--version"))
    if not m:
        raise SystemExit("cannot read the WhiteboxTools version")
    return m.group(1)


def type_of(t) -> tuple[str, list | None]:
    """WhiteboxTools parameter_type -> (type text, allowed values)."""
    if isinstance(t, str):
        return t, None
    if isinstance(t, dict) and len(t) == 1:
        (k, v), = t.items()
        if k == "OptionList":
            return "OptionList", v
        if isinstance(v, str):
            return f"{k}:{v}", None
        if isinstance(v, dict) and len(v) == 1:
            (k2, v2), = v.items()
            return f"{k}:{k2}:{v2}" if isinstance(v2, str) else f"{k}:{k2}", None
        return k, None
    return "any", None


def parameters(wbt: str, tool: str) -> dict:
    data = json.loads(run(wbt, f"--toolparameters={tool}"))
    out = {}
    for p in data.get("parameters", []):
        flags = p.get("flags") or []
        long_flags = [f for f in flags if f.startswith("--")]
        name = (long_flags[-1] if long_flags else flags[-1] if flags else p.get("name", "")).lstrip("-")
        if not name:
            continue
        type_, values = type_of(p.get("parameter_type"))
        note = "output" if type_.startswith("NewFile") else None
        out[name] = common.param(type_, required=not p.get("optional", True),
                                 default=p.get("default_value"), values=values, note=note)
    return out


def harvest(wbt: str) -> tuple[str, list[dict]]:
    ver = version(wbt)
    entries = []
    for line in run(wbt, "--listtools").splitlines():
        m = re.match(r"^([A-Za-z0-9]+):\s", line)
        if not m:
            continue
        tool = m.group(1)
        entries.append(common.entry(
            id=common.slug("whiteboxtools", re.sub(r"(?<!^)(?=[A-Z])", "-", tool)),
            name=tool, software="whiteboxtools", interface="cli", call_name=tool,
            harvester="whitebox", engine_version=ver, parameters=parameters(wbt, tool)))
    return ver, entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--wbt", default="whitebox_tools", help="the whitebox_tools program")
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    ver, entries = harvest(args.wbt)
    common.report("whiteboxtools", ver, common.write("whiteboxtools", entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
