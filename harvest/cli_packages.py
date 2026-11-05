#!/usr/bin/env python3
"""Harvest command-line tool suites by name, from their conda package's file list.

    python harvest/cli_packages.py --prefix ENV

Some suites (TauDEM, the open LAStools programs) print free-form usage text rather
than a machine-readable description, so their parameters cannot be harvested as
facts. These are listed by name only: one implementation per program the conda
package installs in bin/, with no parameters and a note saying so. ENV is a conda
environment with the packages installed; the program list comes from
ENV/conda-meta/<package>-*.json, so nothing is run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

PACKAGES = {  # conda package: registry software id
    "taudem": "taudem",
    "lastools": "lastools",
}
NOTE = "Listed by name: the program prints free-form usage (run it with -h), so its parameters are not harvested."


def harvest(prefix: Path, package: str, software: str) -> tuple[str, list[dict]]:
    metas = sorted((prefix / "conda-meta").glob(f"{package}-[0-9]*.json"))
    if not metas:
        raise SystemExit(f"{package} is not installed in {prefix}")
    meta = json.loads(metas[-1].read_text(encoding="utf-8"))
    programs = sorted({Path(f).name for f in meta.get("files", [])
                       if f.startswith("bin/") and "/" not in f[4:]})
    entries = [common.entry(
        id=common.slug(software, prog), name=prog, software=software, interface="cli", call_name=prog,
        harvester="cli-packages", engine_version=meta["version"], parameters={}, notes=NOTE)
        for prog in programs]
    return meta["version"], entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prefix", type=Path, required=True, help="conda environment with the packages")
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    for package, software in PACKAGES.items():
        ver, entries = harvest(args.prefix, package, software)
        common.report(software, ver, common.write(software, entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
