#!/usr/bin/env python3
"""Harvest PostGIS functions from a database's own catalogue (pg_proc).

    python harvest/postgis.py [--psql PATH] [--dsn CONNINFO]

The database must have the postgis and postgis_raster extensions created; the
harvester only reads the catalogue. Writes implementations/postgis/ (from the
postgis extension) and implementations/postgis-raster/ (from postgis_raster),
one entry per ST_ function, with every overload under `signatures` and the
named arguments under `parameters`. Connection settings come from --dsn or the
usual PG* environment variables.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOFTWARE = {"postgis": "postgis", "postgis_raster": "postgis-raster"}

FUNCTIONS = r"""
SELECT json_build_object(
  'name', p.proname,
  'ext', e.extname,
  'kind', p.prokind,
  'returns', pg_get_function_result(p.oid),
  'args', COALESCE((
    SELECT json_agg(json_build_object(
             'name', NULLIF(a.n, ''),
             'type', format_type(a.t, NULL),
             'default', pg_get_function_arg_default(p.oid, a.pos::int))
           ORDER BY a.pos)
      FROM unnest(COALESCE(p.proallargtypes, p.proargtypes::oid[]), p.proargnames, p.proargmodes)
           WITH ORDINALITY AS a(t, n, m, pos)
     WHERE COALESCE(a.m, 'i') IN ('i', 'b', 'v')), '[]'::json))
FROM pg_proc p
JOIN pg_depend d ON d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e'
JOIN pg_extension e ON e.oid = d.refobjid
WHERE e.extname IN ('postgis', 'postgis_raster') AND p.proname LIKE 'st\_%'
ORDER BY p.proname, pg_get_function_identity_arguments(p.oid);
"""


def query(psql: str, dsn: str | None, sql: str) -> list[str]:
    cmd = [psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", sql]
    if dsn:
        cmd[1:1] = ["-d", dsn]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def harvest(psql: str, dsn: str | None) -> dict[str, tuple[str, list[dict]]]:
    versions = {
        # Some builds append a revision ("3.7.0 3fb2ad1"); keep the release number.
        "postgis": query(psql, dsn, "SELECT postgis_lib_version()")[0].split()[0],
        "postgis-raster": query(psql, dsn, "SELECT postgis_raster_lib_version()")[0].split()[0],
    }
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for line in query(psql, dsn, FUNCTIONS):
        f = json.loads(line)
        grouped[(SOFTWARE[f["ext"]], f["name"])].append(f)
    out: dict[str, tuple[str, list[dict]]] = {s: (versions[s], []) for s in versions}
    for (software, name), overloads in sorted(grouped.items()):
        params: dict[str, dict] = {}
        signatures = []
        aggregate = False
        for f in overloads:
            args = []
            for a in f["args"]:
                arg = {"type": a["type"]}
                if a["name"]:
                    arg = {"name": a["name"], **arg}
                    p = params.setdefault(a["name"], {"types": [], "defaults": set()})
                    if a["type"] not in p["types"]:
                        p["types"].append(a["type"])
                if a["default"] is not None:
                    arg["default"] = a["default"]
                    if a["name"]:
                        params[a["name"]]["defaults"].add(a["default"])
                args.append(arg)
            returns = f["returns"] + (" (aggregate)" if f["kind"] == "a" else "")
            aggregate = aggregate or f["kind"] == "a"
            signatures.append({"arguments": args, "returns": returns})
        parameters = {
            n: common.param(" | ".join(p["types"]),
                            default=next(iter(p["defaults"])) if len(p["defaults"]) == 1 else None)
            for n, p in params.items()
        }
        out[software][1].append(common.entry(
            id=common.slug(software, name), name=name, software=software, interface="sql",
            call_name=name, harvester="postgis", engine_version=versions[software],
            parameters=parameters, signatures=signatures,
            notes="Has an aggregate form." if aggregate else None))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--psql", default="psql", help="the psql program (default: psql on PATH)")
    ap.add_argument("--dsn", help="connection string; default: PG* environment variables")
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    for software, (ver, entries) in harvest(args.psql, args.dsn).items():
        common.report(software, ver, common.write(software, entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
