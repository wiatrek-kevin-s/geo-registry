#!/usr/bin/env python3
"""Convert the Geospatial Tool Atlas CSV into geo-registry YAML entries.

Reproducible and deterministic: running it twice on the same CSV produces
byte-identical files. Requires Python 3.12+ and PyYAML; nothing else.

Usage:
    python seed/convert.py                 # regenerate entries/ from the seed CSV
    python seed/convert.py --check         # regenerate to a temp dir and diff against entries/
    python seed/convert.py --csv FILE --out DIR

The CSV is treated strictly as data. Nothing in it is executed or fetched.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO_ROOT / "seed" / "geospatial-tool-atlas.csv"
DEFAULT_OUT = REPO_ROOT / "entries"
SOURCE_NAME = "geospatial-tool-atlas"

EXPECTED_COLUMNS = [
    "category", "subcategory", "name", "kind", "open_source", "license", "language",
    "what_it_does", "interfaces", "status", "url", "notes", "also",
]

# --------------------------------------------------------------------------- #
# Licences
# --------------------------------------------------------------------------- #

# SPDX licence identifiers we accept as-is (a subset of the SPDX list that covers
# the atlas plus common neighbours). Deprecated ids such as GPL-3.0 are valid SPDX
# and are kept unchanged: whether the atlas meant "-only" or "-or-later" is not
# knowable from the text, so a reviewer should settle it.
SPDX_IDS = frozenset("""
0BSD AGPL-3.0 AGPL-3.0-only AGPL-3.0-or-later Apache-1.1 Apache-2.0 Artistic-2.0
Beerware BSD-2-Clause BSD-3-Clause BSD-4-Clause BSL-1.0 BUSL-1.1 CC-BY-3.0 CC-BY-4.0
CC-BY-NC-4.0 CC-BY-NC-SA-4.0 CC-BY-ND-4.0 CC-BY-SA-3.0 CC-BY-SA-4.0 CC0-1.0
CDLA-Permissive-1.0 CDLA-Permissive-2.0 CECILL-2.1 CECILL-B CECILL-C curl
Elastic-2.0 EPL-1.0 EPL-2.0 EUPL-1.1 EUPL-1.2 GPL-2.0 GPL-2.0-only GPL-2.0-or-later
GPL-3.0 GPL-3.0-only GPL-3.0-or-later Hippocratic-2.1 ISC LGPL-2.0 LGPL-2.0-only
LGPL-2.0-or-later LGPL-2.1 LGPL-2.1-only LGPL-2.1-or-later LGPL-3.0 LGPL-3.0-only
LGPL-3.0-or-later libtiff MIT MIT-0 MPL-1.1 MPL-2.0 NASA-1.3 ODbL-1.0 ODC-By-1.0
OFL-1.1 PDDL-1.0 PostgreSQL Python-2.0 SSPL-1.0 Unlicense UPL-1.0 WTFPL X11 Zlib
""".split())

SPDX_EXCEPTIONS = frozenset("""
Classpath-exception-2.0 GCC-exception-3.1 LGPL-3.0-linking-exception LLVM-exception
OCaml-LGPL-linking-exception
""".split())

# Whole-string aliases (exact match after trimming).
LICENSE_ALIASES = {
    "Apache 2.0": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "BSD-3": "BSD-3-Clause",
    "BSD-2": "BSD-2-Clause",
    "GPL v2+": "GPL-2.0-or-later",
    "GPL v3+": "GPL-3.0-or-later",
    "MIT / Apache-2.0": "MIT OR Apache-2.0",
    # The atlas does not say which exception, so no SPDX exception id can be chosen.
    "GPL-2.0-or-later WITH linking exception": "LicenseRef-GPL-2.0-or-later-with-linking-exception",
}

# Token aliases applied inside an otherwise valid expression.
LICENSE_TOKEN_ALIASES = {
    "BSL-1.1": "BUSL-1.1",          # Business Source License; "BSL-1.0" is Boost
    "SSPLv1": "SSPL-1.0",
    "ODbL": "ODbL-1.0",
    "RSALv2": "LicenseRef-RSALv2",
    "FTWPL": "LicenseRef-FTWPL",
}

NOASSERTION_WORDS = {"", "unknown", "n/a", "n/a (convention)", "none", "tbd"}

LICENSEREF_RE = re.compile(r"^LicenseRef-[A-Za-z0-9.\-]+$")


def _token_ok(tok: str) -> bool:
    return tok in SPDX_IDS or bool(LICENSEREF_RE.match(tok))


def parse_spdx(expr: str) -> str | None:
    """Return a canonical SPDX expression if `expr` is one (after token aliases)."""
    raw = re.findall(r"\(|\)|[^\s()]+", expr)
    if not raw:
        return None
    out: list[str] = []
    expect_operand = True
    depth = 0
    prev_with = False
    for tok in raw:
        if tok == "(":
            if not expect_operand:
                return None
            depth += 1
            out.append(tok)
        elif tok == ")":
            if expect_operand or depth == 0:
                return None
            depth -= 1
            out.append(tok)
        elif tok in ("AND", "OR", "WITH"):
            if expect_operand:
                return None
            prev_with = tok == "WITH"
            expect_operand = True
            out.append(tok)
        else:
            if not expect_operand:
                return None
            if prev_with:
                if tok not in SPDX_EXCEPTIONS:
                    return None
                prev_with = False
            else:
                tok = LICENSE_TOKEN_ALIASES.get(tok, tok)
                if not _token_ok(tok):
                    return None
            out.append(tok)
            expect_operand = False
    if expect_operand or depth != 0:
        return None
    s = " ".join(out)
    return s.replace("( ", "(").replace(" )", ")")


@dataclass(frozen=True)
class LicenseResult:
    value: str
    bucket: str  # unchanged | spdx-normalised | licenseref | noassertion


def normalise_license(original: str) -> LicenseResult:
    text = original.strip()
    if text.lower() in NOASSERTION_WORDS:
        return LicenseResult("NOASSERTION", "noassertion")
    if text in LICENSE_ALIASES:
        value = LICENSE_ALIASES[text]
        return LicenseResult(value, "licenseref" if value.startswith("LicenseRef-") else "spdx-normalised")
    parsed = parse_spdx(text)
    if parsed is not None:
        return LicenseResult(parsed, "unchanged" if parsed == text else "spdx-normalised")
    low = text.lower()
    # Several licences for different components (code vs data, editions, ...).
    # Separators inside parentheses are part of a qualifier, not a list.
    outer = re.sub(r"\([^()]*\)", "", text)
    if ";" in outer or " / " in outer or low.startswith(("mixed", "varies", "various")):
        return LicenseResult("LicenseRef-Multiple", "licenseref")
    # "BSD-3-Clause (Unidata)", "MIT (GDAL)", "libtiff (BSD-like)": a single SPDX
    # licence with a qualifier about who/what it applies to.
    m = re.match(r"^(?P<lic>[^()]+?)\s*\((?P<q>[^()]*)\)$", text)
    if m:
        parsed = parse_spdx(m.group("lic"))
        qualifier = m.group("q").lower()
        if parsed is not None and "proprietary" not in qualifier:
            if "commercial" in qualifier:
                # e.g. "GPL-3.0-or-later OR LGPL-3.0-or-later (dual commercial)"
                return LicenseResult(f"{parsed} OR LicenseRef-Commercial", "spdx-normalised")
            return LicenseResult(parsed, "spdx-normalised")
    prefixes = [
        ("proprietary", "LicenseRef-Proprietary"),
        ("public domain", "LicenseRef-Public-Domain"),
        ("public (", "LicenseRef-Open-Specification"),
        ("ogc document licence", "LicenseRef-OGC-Document"),
        ("w3c document licence", "LicenseRef-W3C-Document"),
        ("open standard", "LicenseRef-Open-Specification"),
        ("open specification", "LicenseRef-Open-Specification"),
        ("open conventions", "LicenseRef-Open-Specification"),
        ("open national standards", "LicenseRef-Open-Specification"),
        ("open (", "LicenseRef-Open-Specification"),
        ("iso standard", "LicenseRef-ISO-Standard"),
        ("copernicus dem licence", "LicenseRef-Copernicus-DEM"),
        ("copernicus", "LicenseRef-Copernicus"),
        ("jaxa", "LicenseRef-JAXA"),
        ("custom", "LicenseRef-Custom"),
    ]
    for prefix, ref in prefixes:
        if low.startswith(prefix):
            return LicenseResult(ref, "licenseref")
    return LicenseResult("NOASSERTION", "noassertion")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def slugify(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "entry"


def clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


PROJECT_STATUS = {
    "Active": "active",
    "Maintained": "maintained",
    "Low activity": "low-activity",
    "Unknown": "unknown",
    "Archived/Deprecated": "archived",
}

OPEN_SOURCE = {"Yes": "yes", "No": "no", "Partial": "partial"}

# Atlas interface label -> `call` value. GUI and n/a are not programmatic calls.
CALL_MAP = {
    "Python": "python", "CLI": "cli", "REST": "rest", "JS": "js", "R": "r", "SQL": "sql",
    "MCP": "mcp", "OGC": "ogc", "STAC": "stac", "C/C++": "c-cpp", "Rust": "rust",
    "Java": "java", ".NET": "dotnet", "Go": "go", "JDBC": "jdbc", "Julia": "julia",
    "plugin": "plugin", "download": "download",
}
CALL_ORDER = list(dict.fromkeys(CALL_MAP.values()))

# Install hints: only package names the atlas notes state explicitly.
INSTALL_PATTERNS = [
    ("pip", re.compile(r"\bpip install ([A-Za-z0-9][A-Za-z0-9._-]*)")),
    ("pip", re.compile(r"\bpip package ([A-Za-z0-9][A-Za-z0-9._-]*)")),
    ("pip", re.compile(r"\bPyPI ([a-z0-9][a-z0-9._-]*)")),
    ("pip", re.compile(r"\bnpm/PyPI ([a-z0-9][a-z0-9._-]*)")),
    ("npm", re.compile(r"\bnpm/PyPI ([a-z0-9][a-z0-9._-]*)")),
    ("npm", re.compile(r"\bnpm install ([@A-Za-z0-9][A-Za-z0-9./_-]*)")),
    ("conda_forge", re.compile(r"\bconda install (?:-c conda-forge )?([A-Za-z0-9][A-Za-z0-9._-]*)")),
    ("cargo", re.compile(r"\bcargo install ([A-Za-z0-9][A-Za-z0-9._-]*)")),
    ("winget", re.compile(r"\bwinget install ([A-Za-z0-9][A-Za-z0-9._-]*)")),
]
INSTALL_STOPWORDS = {"release", "releases", "package", "packages", "version", "wheel", "wheels"}
INSTALL_ORDER = ["winget", "conda_forge", "pip", "npm", "cargo"]


def extract_install(notes: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for key, pat in INSTALL_PATTERNS:
        m = pat.search(notes)
        if m and m.group(1).lower() not in INSTALL_STOPWORDS and key not in found:
            found[key] = m.group(1).rstrip(".,;")
    return {k: found[k] for k in INSTALL_ORDER if k in found}


def access_type_for(url: str) -> str:
    """Pick an access type only when the URL makes it obvious; default http."""
    low = url.lower()
    path = re.sub(r"^[a-z]+://[^/]+", "", low)
    if low.startswith("s3://"):
        return "s3"
    if re.search(r"/(featureserver|mapserver|imageserver|vectortileserver)(/|$)", path):
        return "arcgis-rest"
    if re.search(r"(^|[/_.-])stac([/_.-]|$)", path):
        return "stac"
    if re.search(r"service=wms", low):
        return "ogc-wms"
    if re.search(r"service=wmts", low):
        return "ogc-wmts"
    if re.search(r"service=wfs", low):
        return "ogc-wfs"
    if re.search(r"service=wcs", low):
        return "ogc-wcs"
    if re.search(r"\.ept\.json$|/ept\.json$", path):
        return "ept"
    return "http"


REGION_PATTERNS = [
    ("Texas", re.compile(r"\b(Texas|TxDOT|TxGIO|TWDB|TCEQ|Travis County|Austin|Houston)\b")),
    ("United States", re.compile(r"\b(US|U\.S\.|USA|United States|CONUS|continental US|nationwide)\b")),
    ("Netherlands", re.compile(r"\bNetherlands\b")),
    ("North America", re.compile(r"\bNorth America\b")),
    ("Europe", re.compile(r"\b(Europe|European|Pan-European)\b")),
    # Other continents are not regions we emit; a hit forces "Unspecified".
    ("_other", re.compile(r"\b(Africa|Asia|Latin America|South America|Australia|Oceania)\b")),
    ("Global", re.compile(r"\b([Gg]lobal|worldwide|continent|[Nn]ear-global|[Qq]uasi-global|every country)\b")),
]


def infer_region(row: dict[str, str]) -> str:
    """Conservative coverage guess from the name, summary and subcategory.

    The atlas `notes` column is commentary from the atlas author (e.g. "useful
    for Austin work") and is deliberately ignored here.
    """
    sub = row["subcategory"]
    text = " ".join([row["name"], row["what_it_does"]])
    hits = {name for name, pat in REGION_PATTERNS if pat.search(text)}
    if sub == "Texas":
        return "Texas" if hits <= {"Texas", "United States"} else "Unspecified"
    if "Texas" in hits:
        hits.discard("United States")
    if sub.startswith("US federal") and not hits and re.search(r"\b[Nn]ational\b", text):
        hits.add("United States")
    if sub.startswith("Global") and not hits:
        hits.add("Global")
    if len(hits) == 1 and "_other" not in hits:
        return hits.pop()
    return "Unspecified"


# Publisher only when the entry name makes it obvious.
PUBLISHER_PREFIXES = [
    ("USGS", "U.S. Geological Survey"),
    ("NOAA", "National Oceanic and Atmospheric Administration"),
    ("NASA", "NASA"),
    ("FEMA", "Federal Emergency Management Agency"),
    ("USFWS", "U.S. Fish and Wildlife Service"),
    ("USFS", "U.S. Forest Service"),
    ("NPS", "National Park Service"),
    ("BLM", "Bureau of Land Management"),
    ("EPA", "U.S. Environmental Protection Agency"),
    ("BTS", "Bureau of Transportation Statistics"),
    ("FHWA", "Federal Highway Administration"),
    ("FAA", "Federal Aviation Administration"),
    ("FCC", "Federal Communications Commission"),
    ("Census", "U.S. Census Bureau"),
    ("TxGIO", "Texas Geographic Information Office"),
    ("TxDOT", "Texas Department of Transportation"),
    ("TCEQ", "Texas Commission on Environmental Quality"),
    ("Texas Water Development Board", "Texas Water Development Board"),
    ("Railroad Commission of Texas", "Railroad Commission of Texas"),
    ("Texas Parks and Wildlife", "Texas Parks and Wildlife Department"),
    ("Texas General Land Office", "Texas General Land Office"),
    ("Texas Historical Commission", "Texas Historical Commission"),
    ("Texas DSHS", "Texas Department of State Health Services"),
    ("City of Austin", "City of Austin"),
    ("Travis County", "Travis County"),
    ("Travis Central Appraisal District", "Travis Central Appraisal District"),
    ("CAPCOG", "Capital Area Council of Governments"),
    ("CapMetro", "Capital Metropolitan Transportation Authority"),
    ("H-GAC", "Houston-Galveston Area Council"),
    ("Overture", "Overture Maps Foundation"),
    ("Microsoft", "Microsoft"),
    ("Google", "Google"),
    ("Esri", "Esri"),
    ("ArcGIS", "Esri"),
    ("ESA", "European Space Agency"),
    ("JRC", "European Commission Joint Research Centre"),
    ("Foursquare", "Foursquare"),
    ("Maxar", "Maxar"),
    ("Planet ", "Planet Labs"),
    ("Geofabrik", "Geofabrik"),
    ("OpenStreetMap", "OpenStreetMap Foundation"),
    ("Planet OSM", "OpenStreetMap Foundation"),
]
COMPANY_SUBCATEGORIES = {"Commercial", "Commercial imagery providers"}


def infer_publisher(row: dict[str, str]) -> str:
    name = row["name"]
    # Longest matching prefix wins so "Planet OSM" beats "Planet ".
    best = ""
    publisher = ""
    for prefix, pub in PUBLISHER_PREFIXES:
        if (name.startswith(prefix + " ") or name == prefix or
                (prefix.endswith(" ") and name.startswith(prefix))) and len(prefix) > len(best):
            best, publisher = prefix, pub
    if publisher:
        return publisher
    if row["subcategory"] in COMPANY_SUBCATEGORIES:
        return re.sub(r"\s*\(.*?\)\s*", " ", name).strip()
    return "Unknown"


# --------------------------------------------------------------------------- #
# Conversion
# --------------------------------------------------------------------------- #


@dataclass
class Report:
    rows: int = 0
    per_kind: Counter = field(default_factory=Counter)
    per_atlas_kind: Counter = field(default_factory=Counter)
    license_buckets: Counter = field(default_factory=Counter)
    license_changes: Counter = field(default_factory=Counter)
    duplicates: list[tuple[str, str, int]] = field(default_factory=list)  # (base id, new id, row)
    skipped: list[tuple[int, str]] = field(default_factory=list)
    related_resolved: int = 0
    related_dropped: Counter = field(default_factory=Counter)
    also_categories: int = 0
    same_url: list[tuple[str, list[str]]] = field(default_factory=list)
    no_url_tools: list[str] = field(default_factory=list)
    install_hints: int = 0
    regions: Counter = field(default_factory=Counter)


def read_rows(csv_path: Path) -> list[tuple[int, dict[str, str]]]:
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise SystemExit(f"unexpected CSV header: {reader.fieldnames}")
        # Spreadsheet row numbering: header is row 1, first data row is row 2.
        return [(i, {k: (v or "") for k, v in r.items() if k is not None})
                for i, r in enumerate(reader, start=2)]


def split_list(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"[;,]", text) if p.strip()]


def convert(csv_path: Path) -> tuple[dict[str, dict], Report]:
    rep = Report()
    rows = read_rows(csv_path)
    rep.rows = len(rows)

    # Pass 1: assign ids.
    ids: list[str | None] = []
    used: set[str] = set()
    for row_no, row in rows:
        if not clean(row["name"]):
            rep.skipped.append((row_no, "empty name"))
            ids.append(None)
            continue
        if row["kind"] == "Data source" and not clean(row["url"]):
            rep.skipped.append((row_no, "data source without a URL (access cannot be filled)"))
            ids.append(None)
            continue
        base = slugify(row["name"])
        new = base
        n = 2
        while new in used:
            new = f"{base}-{n}"
            n += 1
        if new != base:
            rep.duplicates.append((base, new, row_no))
        used.add(new)
        ids.append(new)

    name_to_id: dict[str, str] = {}
    for (row_no, row), eid in zip(rows, ids):
        if eid:
            name_to_id.setdefault(clean(row["name"]).casefold(), eid)
    category_names = {clean(r["category"]) for _, r in rows}

    entries: dict[str, dict] = {}
    by_url: dict[tuple[str, str], list[str]] = {}
    for (row_no, row), eid in zip(rows, ids):
        if eid is None:
            continue
        lic = normalise_license(row["license"])
        rep.license_buckets[lic.bucket] += 1
        if lic.value != clean(row["license"]):
            rep.license_changes[(clean(row["license"]), lic.value)] += 1
        review = {"state": "seeded", "source": SOURCE_NAME, "source_row": row_no}
        status = "retired" if row["status"] == "Archived/Deprecated" else "active"
        url = clean(row["url"])
        notes = clean(row["notes"])
        rep.per_atlas_kind[row["kind"]] += 1

        if row["kind"] == "Data source":
            region = infer_region(row)
            rep.regions[region] += 1
            # Data rows' `also` lists extra atlas categories; they become extra themes.
            also_cats = [c.strip() for c in clean(row["also"]).split(";")
                         if c.strip() in category_names]
            rep.also_categories += len(also_cats)
            themes = list(dict.fromkeys(
                slugify(x) for x in (row["subcategory"], row["category"], *also_cats)
                if clean(x)))
            e: dict = {
                "id": eid,
                "kind": "data",
                "name": clean(row["name"]),
                "summary": clean(row["what_it_does"]),
                "publisher": infer_publisher(row),
                "themes": themes,
                "coverage": {"region": region},
                "license": lic.value,
            }
            if lic.value != clean(row["license"]):
                e["license_original"] = clean(row["license"])
            e["access"] = [{"type": access_type_for(url), "url": url, "auth": "none"}]
            if notes:
                e["notes"] = notes
            e["status"] = status
            e["review"] = review
            rep.per_kind["data"] += 1
            folder = "data"
        else:
            interfaces = [x.strip() for x in row["interfaces"].split(";")
                          if x.strip() and x.strip().lower() != "n/a"]
            call = sorted({CALL_MAP[x] for x in interfaces if x in CALL_MAP},
                          key=CALL_ORDER.index)
            related: list[str] = []
            also_cats: list[str] = []
            also = clean(row["also"])
            if also:
                # The atlas `also` column mostly lists other *categories* (some of
                # which contain commas), so match whole ';'-separated categories
                # first, then resolve the remaining comma/semicolon parts as names.
                rest: list[str] = []
                for part in [p.strip() for p in also.split(";") if p.strip()]:
                    if part in category_names:
                        if part != clean(row["category"]):
                            also_cats.append(part)
                    else:
                        rest.extend(split_list(part))
                for name in rest:
                    rid = name_to_id.get(name.casefold())
                    if rid and rid != eid:
                        related.append(rid)
                    else:
                        rep.related_dropped[name] += 1
                related = list(dict.fromkeys(related))
                also_cats = list(dict.fromkeys(also_cats))
                rep.related_resolved += len(related)
                rep.also_categories += len(also_cats)
            install = extract_install(notes)
            if install:
                rep.install_hints += 1
            language = clean(row["language"])
            e = {
                "id": eid,
                "kind": "tool",
                "name": clean(row["name"]),
                "category": clean(row["category"]),
                "subcategory": clean(row["subcategory"]),
                "tool_kind": clean(row["kind"]),
                "summary": clean(row["what_it_does"]),
                "open_source": OPEN_SOURCE[row["open_source"]],
                "license": lic.value,
            }
            if lic.value != clean(row["license"]):
                e["license_original"] = clean(row["license"])
            if language and language.lower() not in ("n/a", "unknown"):
                e["language"] = language
            e["interfaces"] = interfaces
            e["call"] = call
            if install:
                e["install"] = install
            e["wrapped_by_columbus"] = False
            e["project_status"] = PROJECT_STATUS[row["status"]]
            if url:
                e["url"] = url
            else:
                rep.no_url_tools.append(eid)
            if notes:
                e["notes"] = notes
            if related:
                e["related"] = related
            if also_cats:
                e["also_categories"] = also_cats
            e["status"] = status
            e["review"] = review
            rep.per_kind["tool"] += 1
            folder = "tools"
        entries[f"{folder}/{eid}.yaml"] = e
        if url:
            by_url.setdefault((e["kind"], url.rstrip("/").lower()), []).append(eid)

    rep.same_url = sorted(
        (f"{k[0]}: {k[1]}", v) for k, v in by_url.items() if len(v) > 1)
    return entries, rep


class _Dumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper: yaml.SafeDumper, data: str):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _str_presenter)


def dump_yaml(entry: dict) -> str:
    return yaml.dump(entry, Dumper=_Dumper, sort_keys=False, allow_unicode=True,
                     default_flow_style=False, width=100, indent=2)


def write_entries(entries: dict[str, dict], out: Path) -> None:
    for sub in ("data", "tools"):
        d = out / sub
        if d.exists():
            for f in d.glob("*.yaml"):
                f.unlink()
        d.mkdir(parents=True, exist_ok=True)
    for rel in sorted(entries):
        (out / rel).write_text(dump_yaml(entries[rel]), encoding="utf-8", newline="\n")


def diff_dirs(expected: Path, actual: Path) -> list[str]:
    problems: list[str] = []
    exp = {p.relative_to(expected).as_posix() for p in expected.glob("*/*.yaml")}
    act = {p.relative_to(actual).as_posix() for p in actual.glob("*/*.yaml")} if actual.exists() else set()
    for rel in sorted(exp - act):
        problems.append(f"missing in entries/: {rel}")
    for rel in sorted(act - exp):
        problems.append(f"not produced by converter: {rel}")
    for rel in sorted(exp & act):
        a = (expected / rel).read_text(encoding="utf-8")
        b = (actual / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        if a != b:
            d = difflib.unified_diff(b.splitlines(), a.splitlines(),
                                     f"entries/{rel}", f"generated/{rel}", lineterm="", n=1)
            problems.append("\n".join(list(d)[:40]))
    return problems


def print_summary(rep: Report) -> None:
    p = print
    p(f"rows read: {rep.rows}")
    p(f"entries written: {sum(rep.per_kind.values())} "
      f"(data {rep.per_kind['data']}, tool {rep.per_kind['tool']})")
    p("atlas kinds: " + ", ".join(f"{k} {v}" for k, v in sorted(rep.per_atlas_kind.items())))
    p("data coverage.region: " + ", ".join(f"{k} {v}" for k, v in sorted(rep.regions.items())))
    p("licences: " + ", ".join(f"{k} {v}" for k, v in sorted(rep.license_buckets.items())))
    if rep.license_changes:
        p("licence rewrites (original -> value, count), top 25:")
        for (orig, new), n in sorted(rep.license_changes.items(), key=lambda kv: (-kv[1], kv[0]))[:25]:
            p(f"  {orig!r} -> {new} ({n})")
    p(f"duplicate ids (suffixed): {len(rep.duplicates)}")
    for base, new, row in rep.duplicates:
        p(f"  row {row}: {base} -> {new}")
    p(f"same URL within a kind (possible duplicates for review): {len(rep.same_url)}")
    for key, ids in rep.same_url:
        p(f"  {key}: {', '.join(ids)}")
    p(f"related ids resolved: {rep.related_resolved}; "
      f"also -> also_categories: {rep.also_categories}; "
      f"unresolved also names dropped: {sum(rep.related_dropped.values())}")
    for name, n in sorted(rep.related_dropped.items()):
        p(f"  dropped: {name!r} ({n})")
    p(f"tools without a URL (url omitted): {len(rep.no_url_tools)}")
    p(f"tools with install hints from notes: {rep.install_hints}")
    p(f"rows skipped: {len(rep.skipped)}")
    for row, why in rep.skipped:
        p(f"  row {row}: {why}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true",
                    help="regenerate into a temp dir and diff against --out; exit 1 on drift")
    ap.add_argument("--quiet", action="store_true", help="suppress the summary")
    args = ap.parse_args(argv)

    if sys.version_info < (3, 12):
        print("convert.py needs Python 3.12+", file=sys.stderr)
        return 2

    entries, rep = convert(args.csv)
    if not args.quiet:
        print_summary(rep)

    if args.check:
        tmp = Path(tempfile.mkdtemp(prefix="geo-registry-check-"))
        try:
            write_entries(entries, tmp)
            problems = diff_dirs(tmp, args.out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if problems:
            print(f"\nCHECK FAILED: {len(problems)} difference(s) between the converter output "
                  f"and {args.out}", file=sys.stderr)
            for prob in problems[:20]:
                print(prob, file=sys.stderr)
            return 1
        print(f"\ncheck ok: {args.out} matches converter output")
        return 0

    write_entries(entries, args.out)
    print(f"\nwrote {len(entries)} entries to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
