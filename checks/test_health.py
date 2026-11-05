"""Tests for checks/health.py against a local HTTP server (no internet needed).

    python -m unittest checks/test_health.py
"""

from __future__ import annotations

import datetime as dt
import http.server
import json
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import health  # noqa: E402

ROUTES = {
    "/robots.txt": (200, "text/plain", "User-agent: *\nDisallow: /private\n"),
    "/page": (200, "text/html", "<html>ok</html>"),
    "/file.zip": (200, "application/zip", "PK"),
    "/wfs": (200, "text/xml", "<wfs:WFS_Capabilities><FeatureType><Name>ns:roads</Name></FeatureType></wfs:WFS_Capabilities>"),
    "/api": (200, "application/json", json.dumps({"links": []})),
    "/api/collections": (200, "application/json", json.dumps({"collections": [{"id": "roads"}]})),
    "/stac": (200, "application/json", json.dumps({"type": "Catalog", "stac_version": "1.0.0"})),
    "/stac/collections/lidar": (200, "application/json", json.dumps({"type": "Collection"})),
    "/ept/ept.json": (200, "application/json", json.dumps({"bounds": [], "points": 5, "schema": [], "srs": {}})),
    "/arcgis/MapServer/28": (200, "application/json", json.dumps({"name": "Flood zones"})),
    "/arcgis/broken": (200, "application/json", json.dumps({"error": {"code": 500}})),
    "/private/page": (200, "text/html", "secret"),
}


class Handler(http.server.BaseHTTPRequestHandler):
    def _route(self):
        path = self.path.split("?")[0]
        return ROUTES.get(path)

    def do_HEAD(self):
        r = self._route()
        if path_is(self, "/no-head"):
            self.send_response(405)
            self.end_headers()
            return
        self.send_response(r[0] if r else 404)
        if r:
            self.send_header("Content-Type", r[1])
        self.end_headers()

    def do_GET(self):
        r = self._route() or (ROUTES["/page"] if path_is(self, "/no-head") else None)
        self.send_response(r[0] if r else 404)
        if r:
            self.send_header("Content-Type", r[1])
        self.end_headers()
        if r:
            self.wfile.write(r[2].encode())

    def log_message(self, *a):
        pass


def path_is(h, p):
    return h.path.split("?")[0] == p


class HealthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def check(self, *access):
        entry = {"id": "e", "access": [{"auth": "none", **a} for a in access]}
        return health.check_entry(health.Prober(pause=0), entry)

    def test_each_access_type(self):
        b = self.base
        cases = [
            ({"type": "http", "url": f"{b}/page"}, "ok"),
            ({"type": "http", "url": f"{b}/missing"}, "fail"),
            ({"type": "http", "url": f"{b}/no-head"}, "ok"),  # HEAD refused, ranged GET works
            ({"type": "download", "url": f"{b}/file.zip"}, "ok"),
            ({"type": "download", "url": f"{b}/page"}, "fail"),  # an HTML page is not a download
            ({"type": "ogc-wfs", "url": f"{b}/wfs", "index": "ns:roads"}, "ok"),
            ({"type": "ogc-wfs", "url": f"{b}/wfs", "index": "rivers"}, "fail"),
            ({"type": "ogc-api-features", "url": f"{b}/api", "index": "roads"}, "ok"),
            ({"type": "ogc-api-features", "url": f"{b}/api", "index": "rivers"}, "fail"),
            ({"type": "stac", "url": f"{b}/stac", "index": "lidar"}, "ok"),
            ({"type": "stac", "url": f"{b}/page"}, "fail"),
            ({"type": "ept", "url": f"{b}/ept/ept.json"}, "ok"),
            ({"type": "arcgis-rest", "url": f"{b}/arcgis/MapServer", "index": "28"}, "ok"),
            ({"type": "arcgis-rest", "url": f"{b}/arcgis/broken"}, "fail"),
        ]
        for access, want in cases:
            with self.subTest(access=access):
                (r,) = self.check(access)
                self.assertEqual(r.outcome, want, r.detail)

    def test_robots_and_auth_are_skipped(self):
        (r,) = self.check({"type": "http", "url": f"{self.base}/private/page"})
        self.assertEqual((r.outcome, r.detail), ("skipped", "robots.txt disallows it"))
        (r,) = self.check({"type": "http", "url": f"{self.base}/page", "auth": "api-key"})
        self.assertEqual(r.outcome, "skipped")

    def test_unreachable_host_fails(self):
        (r,) = self.check({"type": "http", "url": "http://127.0.0.1:9/x"})
        self.assertEqual(r.outcome, "fail")

    def test_decisions(self):
        today = dt.date(2026, 11, 4)
        ok = [health.Result("e", 0, "http", "u", "ok", "")]
        bad = [health.Result("e", 0, "http", "u", "fail", "HTTP 404")]
        self.assertEqual(health.decide({"status": "active"}, bad, today, 30), {"status": "degraded"})
        self.assertEqual(health.decide({"status": "degraded"}, bad, today, 30), {})  # never straight to retired
        self.assertEqual(health.decide({"status": "degraded", "last_verified": "2026-11-01"}, ok, today, 30),
                         {"status": "active"})
        self.assertEqual(health.decide({"status": "active", "last_verified": "2026-11-01"}, ok, today, 30), {})
        self.assertEqual(health.decide({"status": "active", "last_verified": "2026-09-01"}, ok, today, 30),
                         {"last_verified": "2026-11-04"})

    def test_set_line_keeps_comments(self):
        text = "# a comment\nid: x\nstatus: active\n"
        out = health.set_line(health.set_line(text, "status", "degraded"), "last_verified", "2026-11-04")
        self.assertEqual(out, "# a comment\nid: x\nstatus: degraded\nlast_verified: 2026-11-04\n")


if __name__ == "__main__":
    unittest.main()
