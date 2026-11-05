#!/usr/bin/env python3
"""Harvest GRASS modules from each module's `--interface-description`.

    python harvest/grass.py [--grass PATH]

Starts a throwaway GRASS session (`grass --tmp-project XY`), asks every module in
the installation's bin/ and scripts/ folders to describe itself, and writes
implementations/grass/grass-<module>.yaml, one per module (`v.buffer` becomes
grass-v-buffer). Flags become boolean parameters named flag_<letter>, since a
registry parameter name cannot start with a dash. Modules that cannot describe
themselves without a display (some GUI tools) are skipped and listed.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


# Flags every module has that change only messages or the user interface.
COMMON_FLAGS = {"help", "verbose", "quiet", "ui"}


def clean(s: str | None) -> str | None:
    return " ".join(s.split()) if s and s.strip() else None


def describe(module: str) -> dict:
    out = subprocess.run([module, "--interface-description"], capture_output=True, timeout=60,
                         env={**os.environ, "GRASS_VERBOSE": "-1"})
    if out.returncode != 0 or b"<task" not in out.stdout:
        raise RuntimeError((out.stderr.decode(errors="replace").strip() or "no description")[:200])
    task = ET.fromstring(out.stdout[out.stdout.index(b"<task"):].decode(errors="replace").split("</task>")[0] + "</task>")
    params = {}
    for p in task.findall("parameter"):
        prompt = p.find("gisprompt")
        notes = []
        if prompt is not None and prompt.get("age") == "new":
            notes.append(f"output {prompt.get('element') or ''}".strip())
        elif prompt is not None and prompt.get("element"):
            notes.append(f"{prompt.get('element')} name")
        if p.get("multiple") == "yes":
            notes.append("multiple values")
        values = [clean(v.findtext("name")) for v in p.findall("values/value")]
        type_ = p.get("type") or "string"
        default = clean(p.findtext("default"))
        if default is not None and p.get("multiple") != "yes":
            try:
                default = float(default) if type_ == "float" else int(default) if type_ == "integer" else default
            except ValueError:
                pass
        params[p.get("name")] = common.param(
            type_, required=p.get("required") == "yes", default=default,
            values=[v for v in values if v], note="; ".join(notes) or None)
    for f in task.findall("flag"):
        name = f.get("name")
        if name in COMMON_FLAGS:
            continue
        params[f"flag_{name}"] = common.param("boolean", note=f"flag {'-' if len(name) == 1 else '--'}{name}")
    return params


def inside(out_root: Path, jobs: int) -> int:
    gisbase = Path(os.environ["GISBASE"])
    version = re.search(r"GRASS (\d+\.\d+\.\d+)",
                        subprocess.run(["g.version"], capture_output=True, text=True).stdout).group(1)
    modules = sorted({p.name for d in ("bin", "scripts") if (gisbase / d).is_dir()
                      for p in (gisbase / d).iterdir()
                      if re.fullmatch(r"[a-z0-9]+\.[A-Za-z0-9_.]+", p.name) and not p.name.endswith((".py", ".bat"))})

    def one(module):
        try:
            return module, describe(module), None
        except Exception as e:  # noqa: BLE001 - one module must not stop the harvest
            return module, None, str(e)

    entries, skipped = [], []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for module, params, err in pool.map(one, modules):
            if params is None:
                skipped.append(f"{module}: {err}")
                continue
            entries.append(common.entry(
                id=common.slug("grass", module), name=module, software="grass", interface="cli",
                call_name=module, harvester="grass", engine_version=version, parameters=params))
    common.report("grass", version, common.write("grass", entries, out_root))
    for s in skipped:
        print(f"  skipped {s}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--grass", default="grass", help="the grass program")
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.inside:
        return inside(args.out, args.jobs)
    cmd = [args.grass, "--tmp-project", "XY", "--exec", sys.executable, str(Path(__file__).resolve()),
           "--inside", "--out", str(args.out.resolve()), "--jobs", str(args.jobs)]
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
