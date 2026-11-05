#!/usr/bin/env python3
"""Check that data entries' endpoints still answer, and record the outcome.

    python checks/health.py [--id ID] [--type TYPE] [--report health.json] [--apply]

Each `access` item of each data entry is probed once, read-only and small (see
checks/README.md for what each access type's probe asks and when it passes).
Probes send an identifying User-Agent, respect robots.txt, wait at least one
second between requests to the same host, and never run anything taken from an
entry. Entries whose access needs credentials (auth other than none) and retired
entries are skipped.

With --apply the outcome is written back:
- an entry with a failing access item goes from `active` to `degraded` (never
  straight to `retired`: retiring needs a person);
- a `degraded` entry whose access all passes goes back to `active`;
- `last_verified` is set to today on success when it is missing or older than
  --refresh-days (default 30), so a weekly run does not touch every entry.
Seeded entries are changed through seed/overrides/<id>.yaml (then the converter
is re-run), so the seed's regeneration keeps the change; other entries are
edited in place. Only the `status` and `last_verified` lines are touched.

Standard library and PyYAML only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
USER_AGENT = "geo-registry-health/1 (+https://github.com/wiatrek-kevin-s/geo-registry)"
TIMEOUT = 15
MAX_BODY = 2_000_000  # bytes read from any one response


@dataclass
class Result:
    entry: str
    access: int
    type: str
    url: str
    outcome: str        # ok | fail | skipped
    detail: str
    status: int | None = None
    seconds: float | None = None


class Prober:
    """HTTP access with a per-host pause, robots.txt and a size cap."""

    def __init__(self, pause: float = 1.0, robots: bool = True):
        self.pause = pause
        self.robots = robots
        self.last: dict[str, float] = {}
        self.rules: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _wait(self, host: str) -> None:
        since = time.monotonic() - self.last.get(host, -1e9)
        if since < self.pause:
            time.sleep(self.pause - since)
        self.last[host] = time.monotonic()

    def allowed(self, url: str) -> bool:
        if not self.robots:
            return True
        parts = urllib.parse.urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self.rules:
            rp = urllib.robotparser.RobotFileParser()
            try:
                self._wait(parts.netloc)
                req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                    rp.parse(r.read(200_000).decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as e:
                # No robots.txt (4xx) allows everything; a server error is treated the same.
                rp.parse([] if e.code >= 400 else ["User-agent: *", "Disallow: /"])
            except (urllib.error.URLError, OSError, ValueError):
                rp = None  # unreachable: let the probe itself report the failure
            self.rules[base] = rp
        rp = self.rules[base]
        return rp is None or rp.can_fetch(USER_AGENT, url)

    def get(self, url: str, *, method: str = "GET", accept: str | None = None,
            byte_range: str | None = None) -> tuple[int, bytes, str]:
        parts = urllib.parse.urlsplit(url)
        self._wait(parts.netloc)
        headers = {"User-Agent": USER_AGENT}
        if accept:
            headers["Accept"] = accept
        if byte_range:
            headers["Range"] = byte_range
        req = urllib.request.Request(url, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = b"" if method == "HEAD" else r.read(MAX_BODY)
                return r.status, body, r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            ctype = e.headers.get("Content-Type", "") if e.headers else ""
            e.close()
            return e.code, b"", ctype


def with_query(url: str, **params: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    keys = {k.lower() for k, _ in query}
    query += [(k, v) for k, v in params.items() if k.lower() not in keys]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def join(url: str, *parts: str) -> str:
    return url.rstrip("/") + "/" + "/".join(p.strip("/") for p in parts)


def json_of(body: bytes) -> dict:
    try:
        v = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProbeFail(f"not JSON ({e.__class__.__name__})") from None
    if not isinstance(v, dict):
        raise ProbeFail("JSON is not an object")
    return v


class ProbeFail(Exception):
    pass


def need(status: int, ok=range(200, 400)) -> None:
    if status not in ok:
        raise ProbeFail(f"HTTP {status}")


# One function per access type: returns a short description of what passed, or raises ProbeFail.

def probe_http(p: Prober, a: dict) -> str:
    status, _, _ = p.get(a["url"], method="HEAD")
    if status in (403, 405, 501) or status >= 500:
        status, _, _ = p.get(a["url"], byte_range="bytes=0-1023")
    need(status, range(200, 400) if status != 206 else range(206, 207))
    return f"HTTP {status}"


def probe_download(p: Prober, a: dict) -> str:
    status, _, ctype = p.get(a["url"], method="HEAD")
    if status in (403, 405, 501):
        status, _, ctype = p.get(a["url"], byte_range="bytes=0-1023")
    need(status, range(200, 300))
    if ctype.startswith("text/html"):
        raise ProbeFail("download returned an HTML page")
    return f"HTTP {status} {ctype}".strip()


def probe_ogc(service: str):
    def probe(p: Prober, a: dict) -> str:
        status, body, _ = p.get(with_query(a["url"], SERVICE=service, REQUEST="GetCapabilities"))
        need(status, range(200, 300))
        text = body.decode("utf-8", "replace")
        if "Capabilities" not in text[:5000] or "ExceptionReport" in text[:2000]:
            raise ProbeFail(f"no {service} capabilities document")
        index = a.get("index")
        if index and f">{index}<" not in text and f">{index.split(':')[-1]}<" not in text:
            raise ProbeFail(f"layer {index!r} not listed")
        return f"{service} capabilities" + (f", {index} listed" if index else "")
    return probe


def probe_ogc_api(p: Prober, a: dict) -> str:
    status, body, _ = p.get(with_query(a["url"], f="json"), accept="application/json")
    need(status, range(200, 300))
    json_of(body)
    status, body, _ = p.get(with_query(join(a["url"], "collections"), f="json"), accept="application/json")
    need(status, range(200, 300))
    ids = [c.get("id") for c in json_of(body).get("collections", []) if isinstance(c, dict)]
    if a.get("index") and a["index"] not in ids:
        raise ProbeFail(f"collection {a['index']!r} not listed")
    return f"{len(ids)} collections" + (f", {a['index']} listed" if a.get("index") else "")


def probe_stac(p: Prober, a: dict) -> str:
    status, body, _ = p.get(a["url"], accept="application/json")
    need(status, range(200, 300))
    root = json_of(body)
    if "stac_version" not in root and root.get("type") not in ("Catalog", "Collection"):
        raise ProbeFail("not a STAC catalog or collection")
    if a.get("index"):
        status, body, _ = p.get(join(a["url"], "collections", a["index"]), accept="application/json")
        need(status, range(200, 300))
        json_of(body)
    return f"STAC {root.get('stac_version', '')}".strip() + (f", {a['index']} found" if a.get("index") else "")


def probe_ept(p: Prober, a: dict) -> str:
    url = a.get("index") if str(a.get("index", "")).endswith("ept.json") else a["url"]
    if not url.endswith("ept.json"):
        # The EPT root is a bucket of datasets; its index lists their footprints.
        status, body, _ = p.get(a.get("index") or a["url"], accept="application/json")
        need(status, range(200, 300))
        json_of(body)
        return "EPT index answers"
    status, body, _ = p.get(url, accept="application/json")
    need(status, range(200, 300))
    meta = json_of(body)
    missing = [k for k in ("bounds", "points", "schema", "srs") if k not in meta]
    if missing:
        raise ProbeFail(f"ept.json lacks {', '.join(missing)}")
    return f"EPT, {meta['points']} points"


def probe_arcgis(p: Prober, a: dict) -> str:
    url = join(a["url"], a["index"]) if a.get("index") else a["url"]
    status, body, _ = p.get(with_query(url, f="json"), accept="application/json")
    need(status, range(200, 300))
    meta = json_of(body)
    if "error" in meta:
        raise ProbeFail(f"service error {meta['error'].get('code', '')}".strip())
    return "ArcGIS REST " + (meta.get("name") or meta.get("serviceDescription", "")[:40] or "answers")


def probe_s3(p: Prober, a: dict) -> str:
    m = re.match(r"^s3://([^/]+)/?(.*)$", a["url"])
    if not m:
        raise ProbeFail("not an s3:// URL")
    bucket, prefix = m.groups()
    status, body, _ = p.get(with_query(f"https://{bucket}.s3.amazonaws.com/", **{
        "list-type": "2", "max-keys": "1", "prefix": prefix}))
    need(status, range(200, 300))
    if b"<Key>" not in body:
        raise ProbeFail("bucket listing is empty")
    return "S3 listing"


PROBES = {
    "http": probe_http, "api": probe_http, "other": probe_http,
    "download": probe_download,
    "ogc-wms": probe_ogc("WMS"), "ogc-wmts": probe_ogc("WMTS"),
    "ogc-wfs": probe_ogc("WFS"), "ogc-wcs": probe_ogc("WCS"),
    "ogc-api-features": probe_ogc_api, "ogc-api-tiles": probe_ogc_api,
    "stac": probe_stac, "ept": probe_ept, "arcgis-rest": probe_arcgis, "s3": probe_s3,
}


def check_entry(p: Prober, e: dict, only_type: str | None = None) -> list[Result]:
    out = []
    for i, a in enumerate(e.get("access") or []):
        if only_type and a["type"] != only_type:
            continue
        r = Result(e["id"], i, a["type"], a["url"], "skipped", "")
        if a.get("auth", "none") != "none":
            r.detail = f"needs {a['auth']}"
        elif a["url"].startswith("http") and not p.allowed(a["url"]):
            r.detail = "robots.txt disallows it"
        else:
            start = time.monotonic()
            try:
                r.detail = PROBES[a["type"]](p, a)
                r.outcome = "ok"
            except ProbeFail as ex:
                r.outcome, r.detail = "fail", str(ex)
            except (urllib.error.URLError, OSError, ValueError) as ex:
                r.outcome, r.detail = "fail", f"{type(ex).__name__}: {getattr(ex, 'reason', ex)}"[:200]
            r.seconds = round(time.monotonic() - start, 2)
        out.append(r)
    return out


# ------------------------------------------------------------------ applying

def set_line(text: str, key: str, value: str) -> str:
    """Set a top-level `key: value` line in YAML text, keeping everything else (comments too)."""
    line = f"{key}: {value}"
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.M)
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    return text.rstrip("\n") + "\n" + line + "\n"


def decide(entry: dict, results: list[Result], today: dt.date, refresh_days: int) -> dict[str, str]:
    """The `status` / `last_verified` changes for one entry, or {}."""
    probed = [r for r in results if r.outcome != "skipped"]
    if not probed:
        return {}
    changes: dict[str, str] = {}
    status = entry.get("status", "active")
    if any(r.outcome == "fail" for r in probed):
        if status == "active":
            changes["status"] = "degraded"
        return changes
    if status == "degraded":
        changes["status"] = "active"
    last = entry.get("last_verified")
    if not last or (today - dt.date.fromisoformat(str(last))).days >= refresh_days:
        changes["last_verified"] = today.isoformat()
    return changes


def apply(entries_dir: Path, overrides_dir: Path, entries: dict[str, dict],
          changes: dict[str, dict[str, str]]) -> list[str]:
    touched = []
    seeded = False
    for eid, ch in sorted(changes.items()):
        e = entries[eid]
        is_seed = (e.get("review") or {}).get("source") == "geospatial-tool-atlas"
        path = overrides_dir / f"{eid}.yaml" if is_seed else entries_dir / "data" / f"{eid}.yaml"
        text = path.read_text(encoding="utf-8") if path.exists() else f"id: {eid}\n"
        for k, v in ch.items():
            text = set_line(text, k, v)
        path.write_text(text, encoding="utf-8", newline="\n")
        touched.append(str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path))
        seeded = seeded or is_seed
    if seeded:
        subprocess.run([sys.executable, str(REPO / "seed" / "convert.py"), "--quiet"], check=True)
    return touched


def summary(results: list[Result], changes: dict[str, dict[str, str]]) -> str:
    ok = sum(r.outcome == "ok" for r in results)
    fail = [r for r in results if r.outcome == "fail"]
    skipped = sum(r.outcome == "skipped" for r in results)
    lines = [f"Probed {ok + len(fail)} access items: {ok} answered, {len(fail)} failed, {skipped} skipped.", ""]
    degraded = sorted(e for e, c in changes.items() if c.get("status") == "degraded")
    restored = sorted(e for e, c in changes.items() if c.get("status") == "active")
    verified = sum("last_verified" in c for c in changes.values())
    if degraded:
        lines.append(f"Marked degraded ({len(degraded)}): " + ", ".join(f"`{e}`" for e in degraded))
    if restored:
        lines.append(f"Back to active ({len(restored)}): " + ", ".join(f"`{e}`" for e in restored))
    lines.append(f"last_verified refreshed on {verified} entries.")
    if fail:
        lines += ["", "| Entry | Access | Problem |", "| --- | --- | --- |"]
        lines += [f"| `{r.entry}` | {r.type} {r.url} | {r.detail} |" for r in fail]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--entries", type=Path, default=REPO / "entries")
    ap.add_argument("--overrides", type=Path, default=REPO / "seed" / "overrides")
    ap.add_argument("--id", action="append", help="check only these entries (repeatable)")
    ap.add_argument("--type", help="check only this access type")
    ap.add_argument("--report", type=Path, help="write all results as JSON")
    ap.add_argument("--summary", type=Path, help="write a Markdown summary")
    ap.add_argument("--apply", action="store_true", help="write status and last_verified changes")
    ap.add_argument("--refresh-days", type=int, default=30)
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    args = ap.parse_args()

    entries = {}
    for path in sorted((args.entries / "data").glob("*.yaml")):
        e = yaml.safe_load(path.read_text(encoding="utf-8"))
        if e.get("status") == "retired" or (args.id and e["id"] not in args.id):
            continue
        entries[e["id"]] = e

    prober = Prober()
    results: list[Result] = []
    changes: dict[str, dict[str, str]] = {}
    for eid, e in entries.items():
        rs = check_entry(prober, e, args.type)
        results += rs
        if not args.type:  # a partial check says nothing about the whole entry
            ch = decide(e, rs, args.today, args.refresh_days)
            if ch:
                changes[eid] = ch
        for r in rs:
            print(f"{r.outcome:7} {r.entry:40} {r.type:16} {r.detail}")

    text = summary(results, changes)
    print("\n" + text)
    if args.report:
        args.report.write_text(json.dumps([asdict(r) for r in results], indent=1), encoding="utf-8")
    if args.summary:
        args.summary.write_text(text, encoding="utf-8")
    if args.apply and changes:
        for path in apply(args.entries, args.overrides, entries, changes):
            print(f"updated {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
