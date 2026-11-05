#!/usr/bin/env python3
"""Harvest DuckDB's spatial extension functions from duckdb_functions().

    python harvest/duckdb_spatial.py

Needs the duckdb Python package; the extension itself is installed with
`INSTALL spatial`, which downloads it from extensions.duckdb.org (so this runs in
CI, not on machines without that access). DuckDB does not record which extension
a function came from, so the harvester lists functions before and after
`LOAD spatial` and keeps the ones the extension added. Writes
implementations/duckdb-spatial-extension/, one entry per function name with
every overload under `signatures`.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOFTWARE = "duckdb-spatial-extension"
QUERY = """
SELECT function_name, function_type, return_type, parameters, parameter_types
FROM duckdb_functions()
WHERE function_type IN ('scalar', 'aggregate', 'table', 'macro', 'table_macro')
"""


def rows(con):
    return [r for r in con.execute(QUERY).fetchall()]


def added_by(con, load) -> list:
    """Functions present after calling load(con) that were not there before."""
    before = {(r[0], r[1], str(r[3]), str(r[4])) for r in rows(con)}
    load(con)
    return [r for r in rows(con) if (r[0], r[1], str(r[3]), str(r[4])) not in before]


def harvest() -> tuple[str, list[dict]]:
    import duckdb
    con = duckdb.connect(":memory:")
    added = added_by(con, lambda c: (c.execute("INSTALL spatial"), c.execute("LOAD spatial")))
    version = con.execute(
        "SELECT extension_version FROM duckdb_extensions() WHERE extension_name = 'spatial'").fetchone()[0] or "unknown"
    con.close()
    return str(version), entries_from(added, str(version))


def entries_from(added: list, version: str) -> list[dict]:
    grouped: dict[str, list] = defaultdict(list)
    for r in added:
        grouped[r[0]].append(r)
    entries = []
    for name, overloads in sorted(grouped.items()):
        params: dict[str, dict] = {}
        signatures = []
        kinds = sorted({o[1] for o in overloads})
        for _, kind, ret, pnames, ptypes in overloads:
            args = []
            for i, t in enumerate(ptypes or []):
                n = pnames[i] if pnames and i < len(pnames) else None
                t = str(t) if t is not None else "any"  # macros have no declared types
                arg = {"type": t}
                if n and not str(n).startswith("col"):
                    arg = {"name": str(n), **arg}
                    p = params.setdefault(str(n), [])
                    if str(t) not in p:
                        p.append(str(t))
                args.append(arg)
            signatures.append({"arguments": args, "returns": f"{ret if ret is not None else 'any'}"
                               + ("" if kind == "scalar" else f" ({kind})")})
        entries.append(common.entry(
            id=common.slug("duckdb-spatial", name), name=name, software=SOFTWARE, interface="sql",
            call_name=name, harvester="duckdb-spatial", engine_version=str(version),
            parameters={n: common.param(" | ".join(ts)) for n, ts in params.items()},
            signatures=signatures,
            notes=None if kinds == ["scalar"] else f"Kind: {', '.join(kinds)}."))
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    ver, entries = harvest()
    common.report(SOFTWARE, ver, common.write(SOFTWARE, entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
