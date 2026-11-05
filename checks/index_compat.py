#!/usr/bin/env python3
"""Check that a newly built index is still readable by servers that read the old one.

    python checks/index_compat.py BASE_DIST HEAD_DIST

BASE_DIST is the build of `main`, HEAD_DIST the build of the change. Both hold
registry.sqlite and index.json. The published index is a contract with every
installed Columbus server (README, "Index compatibility"), so a change may add
tables, columns-in-new-tables and keys, but may not alter or remove what is
already there. Content (rows) may change freely.

A change that raises meta.format_version is a declared breaking change: the
check reports it and passes, because Columbus must have been updated first.

Standard library only. Reads the two builds; changes nothing.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Kinds that existing readers expect in the `entries` table.
CATALOGUE_KINDS = {"data", "tool"}


def schema(db: Path) -> dict[str, str]:
    """name -> CREATE statement for user tables and indexes (not FTS shadow tables)."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT name, sql FROM sqlite_master WHERE type IN ('table', 'index') AND sql IS NOT NULL"
        ).fetchall()
        fts = {n for n, s in rows if s.upper().startswith("CREATE VIRTUAL TABLE")}
        shadow = {n for n, _ in rows for f in fts if n != f and n.startswith(f + "_")}
        return {n: " ".join(s.split()) for n, s in rows if n not in shadow}
    finally:
        con.close()


def meta(db: Path) -> dict[str, str]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return dict(con.execute("SELECT key, value FROM meta").fetchall())
    finally:
        con.close()


def entry_kinds(db: Path) -> set[str]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {k for (k,) in con.execute("SELECT DISTINCT kind FROM entries")}
    finally:
        con.close()


def card_keys(index: dict) -> set[str]:
    return {k for c in index.get("entries", []) for k in c}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    base, head = Path(argv[1]), Path(argv[2])
    bdb, hdb = base / "registry.sqlite", head / "registry.sqlite"
    problems: list[str] = []

    bmeta, hmeta = meta(bdb), meta(hdb)
    bver, hver = int(bmeta.get("format_version", "0")), int(hmeta.get("format_version", "0"))
    if hver > bver:
        print(f"format_version {bver} -> {hver}: declared breaking change, compatibility not enforced")
        return 0
    if hver < bver:
        problems.append(f"format_version went down ({bver} -> {hver})")

    bs, hs = schema(bdb), schema(hdb)
    for name, sql in sorted(bs.items()):
        if name not in hs:
            problems.append(f"registry.sqlite: {name} was removed")
        elif hs[name] != sql:
            problems.append(f"registry.sqlite: {name} changed\n  was: {sql}\n  now: {hs[name]}")
    for key in sorted(set(bmeta) - set(hmeta)):
        problems.append(f"registry.sqlite: meta key {key!r} was removed")
    extra = entry_kinds(hdb) - CATALOGUE_KINDS - entry_kinds(bdb)
    if extra:
        problems.append(f"registry.sqlite: entries table now holds kinds {sorted(extra)}; new kinds need their own table")

    bidx = json.loads((base / "index.json").read_text(encoding="utf-8"))
    hidx = json.loads((head / "index.json").read_text(encoding="utf-8"))
    for key in sorted(set(bidx) - set(hidx)):
        problems.append(f"index.json: top-level key {key!r} was removed")
    for key in sorted(card_keys(bidx) - card_keys(hidx)):
        problems.append(f"index.json: card field {key!r} no longer appears on any entry")
    if hidx.get("count") != len(hidx.get("entries", [])):
        problems.append("index.json: count does not match the number of entries")

    added = sorted(set(hs) - set(bs))
    if problems:
        print("index compatibility: FAILED")
        for p in problems:
            print(f"- {p}")
        return 1
    print("index compatibility: ok" + (f" (added: {', '.join(added)})" if added else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
