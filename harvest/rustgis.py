#!/usr/bin/env python3
"""Harvest RustGIS geoprocessing tools from its Python bindings (`Session.tools()`).

    python harvest/rustgis.py

Needs `pip install rustgis` (Apache-2.0; https://rustgis.app). The bindings run the
RustGIS engine headless; `Session().tools()` returns every geoprocessing tool with its
id, name, toolbox and parameters. Writes implementations/rustgis/rustgis-<tool id>.yaml,
called as `Session.run_tool("<id>", ...)`. The tools' summaries are RustGIS's own help
text and are not copied; the toolbox is kept in the note.

Parameter descriptions are read defensively (the shape of `tools()` is not documented
field by field): a parameter's name from `name` or `id`, type from `type` or `kind`,
required from `required` or not `optional`, default from `default`, choices from
`choices`, `options` or `values`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOFTWARE = "rustgis"


def first(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def choices(p: dict) -> list | None:
    c = first(p, "choices", "options", "values", "enum")
    if isinstance(c, dict):
        return list(c.keys())
    if isinstance(c, list):
        return [x.get("value", x.get("id")) if isinstance(x, dict) else x for x in c]
    return None


def parameters(tool: dict) -> dict:
    raw = first(tool, "parameters", "params", default=[])
    if isinstance(raw, dict):  # {name: {...}}
        raw = [{"name": k, **(v if isinstance(v, dict) else {"type": v})} for k, v in raw.items()]
    out = {}
    for p in raw:
        if not isinstance(p, dict):
            continue
        name = first(p, "name", "id", "key")
        if not name:
            continue
        type_ = first(p, "type", "kind", "datatype", default="any")
        if isinstance(type_, (dict, list)):
            type_ = str(type_)
        required = bool(first(p, "required", default=not first(p, "optional", default=True)))
        out[str(name)] = common.param(str(type_), required=required, default=first(p, "default"),
                                      values=choices(p), note="output" if first(p, "output", "is_output") else None)
    return out


def harvest() -> tuple[str, list[dict]]:
    import rustgis
    version = getattr(rustgis, "__version__", None) or "unknown"
    tools = rustgis.Session().tools()
    entries = []
    for t in tools:
        tid = str(first(t, "id", "name"))
        toolbox = first(t, "toolbox", "category", "group")
        entries.append(common.entry(
            id=common.slug("rustgis", tid), name=str(first(t, "name", "id")), software=SOFTWARE,
            interface="python", call_name=tid, harvester="rustgis", engine_version=str(version),
            parameters=parameters(t), notes=f"Toolbox: {toolbox}." if toolbox else None))
    return str(version), entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    ver, entries = harvest()
    common.report(SOFTWARE, ver, common.write(SOFTWARE, entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
