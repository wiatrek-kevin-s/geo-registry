"""Shared helpers for the engine harvesters.

Each harvester asks one engine to describe its own tools and turns the answer
into implementation entries under implementations/<software>/<id>.yaml. Output
is deterministic: the same engine version gives byte-identical files, so a
re-harvest after an engine release shows exactly what changed.

Entries hold facts only: names, types, defaults, choices and required flags,
plus a link the engine itself reports. Engine help text is never copied (the
registry is CC0; engine documentation is under its own licence). The parts a
person writes (which operation, crosswalk, differences, effects) live in
mappings/ and are merged at build time, so re-harvesting never loses them.
"""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent
IMPLEMENTATIONS = REPO / "implementations"

KEY_ORDER = ["id", "kind", "name", "software", "call", "harvest", "parameters",
             "signatures", "docs", "notes", "status", "review"]


def slug(*parts: str) -> str:
    """A registry id: lower-case letters, digits and single hyphens, at most 96 characters."""
    s = "-".join(parts).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > 96:
        s = s[:87].rstrip("-") + "-" + hashlib.sha256(s.encode()).hexdigest()[:8]
    return s


def scalar(v: Any) -> bool:
    """A plain YAML scalar (enum members and other subclasses are not, so they go into notes)."""
    return type(v) in (str, bool, int, float) and not (isinstance(v, float) and not math.isfinite(v))


def describe(v: Any) -> str:
    """A stable description of a non-scalar default: no memory addresses, sets sorted,
    so the same engine version always gives the same text."""
    if callable(v) and hasattr(v, "__qualname__"):
        return f"{getattr(v, '__module__', None) or ''}.{v.__qualname__}".lstrip(".")
    if isinstance(v, (set, frozenset)):
        return "{" + ", ".join(sorted(describe(x) for x in v)) + "}"
    return re.sub(r" at 0x[0-9a-fA-F]+", "", repr(v))


def param(type_: str, *, required: bool = False, default: Any = None,
          values: list | None = None, units: str | None = None, note: str | None = None) -> dict:
    """One engine parameter in the registry's shape. Non-scalar defaults go into the note."""
    p: dict[str, Any] = {"type": type_ or "any"}
    if required:
        p["required"] = True
    if default is not None:
        if scalar(default):
            p["default"] = default
        else:
            note = ((note + "; ") if note else "") + f"default {describe(default)}"[:200]
    if values:
        vals = [v for v in dict.fromkeys(values) if scalar(v)]
        if vals:
            p["values"] = vals
    if units:
        p["units"] = units
    if note:
        p["note"] = note[:300]
    return p


def entry(*, id: str, name: str, software: str, interface: str, call_name: str,
          harvester: str, engine_version: str, parameters: dict,
          signatures: list | None = None, docs: str | None = None, notes: str | None = None) -> dict:
    e: dict[str, Any] = {
        "id": id,
        "kind": "implementation",
        "name": name,
        "software": software,
        "call": {"interface": interface, "name": call_name},
        "harvest": {"harvester": harvester, "engine_version": engine_version},
        "parameters": parameters,
    }
    if signatures:
        e["signatures"] = signatures
    if docs and re.match(r"^https?://\S+$", docs):
        e["docs"] = docs
    if notes:
        e["notes"] = notes
    e["status"] = "active"
    e["review"] = {"state": "harvested", "source": harvester}
    return e


class _Flow(dict):
    """A mapping written on one line ({type: real, required: true})."""


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(_Flow, lambda d, v: d.represent_mapping("tag:yaml.org,2002:map", v.items(), flow_style=True))
_Dumper.add_representer(dict, lambda d, v: d.represent_mapping("tag:yaml.org,2002:map", v.items()))


def _shape(e: dict) -> dict:
    out = {k: e[k] for k in KEY_ORDER if k in e}
    out["call"] = _Flow(out["call"])
    out["harvest"] = _Flow(out["harvest"])
    out["review"] = _Flow(out["review"])
    out["parameters"] = {k: _Flow(v) for k, v in out["parameters"].items()}
    if "signatures" in out:
        out["signatures"] = [
            {"arguments": [_Flow(a) for a in s["arguments"]], **({"returns": s["returns"]} if "returns" in s else {})}
            for s in out["signatures"]
        ]
    return out


def dump(e: dict) -> str:
    return yaml.dump(_shape(e), Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=120)


def reserved_ids() -> set[str]:
    """Ids of the registry's other entries (data, tools, operations). An implementation
    may not reuse one: ids are unique across the whole registry."""
    return {p.stem for sub in ("data", "tools", "operations") for p in (REPO / "entries" / sub).glob("*.yaml")}


def write(software: str, entries: list[dict], root: Path = IMPLEMENTATIONS) -> dict[str, int]:
    """Replace implementations/<software>/ with these entries. Returns counts of changes."""
    folder = root / software
    folder.mkdir(parents=True, exist_ok=True)
    taken = reserved_ids()
    for e in entries:
        if e["id"] in taken:  # e.g. terra::draw vs the Terra Draw library's entry
            e["id"] = e["id"] + "-impl"
    ids = [e["id"] for e in entries]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"{software}: duplicate ids {sorted(dupes)}")
    counts = {"added": 0, "changed": 0, "unchanged": 0, "removed": 0}
    keep = set()
    for e in sorted(entries, key=lambda e: e["id"]):
        path = folder / f"{e['id']}.yaml"
        keep.add(path.name)
        text = dump(e)
        if not path.exists():
            counts["added"] += 1
        elif path.read_text(encoding="utf-8") != text:
            counts["changed"] += 1
        else:
            counts["unchanged"] += 1
            continue
        path.write_text(text, encoding="utf-8", newline="\n")
    for old in folder.glob("*.yaml"):
        if old.name not in keep:
            old.unlink()
            counts["removed"] += 1
    return counts


def report(software: str, version: str, counts: dict[str, int]) -> None:
    total = counts["added"] + counts["changed"] + counts["unchanged"]
    print(f"{software} {version}: {total} implementations "
          f"({counts['added']} added, {counts['changed']} changed, {counts['removed']} removed)")
