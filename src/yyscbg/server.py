"""本地筛选服务：静态页面 + JSON 接口（纯标准库）。"""

from __future__ import annotations

import json
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import store
from .config import FOUR_PIECE_SUITS, HOST, PORT, THRESHOLDS, WEB_DIR


def _num(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = "yys-cbg/0.1"

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, relative: str) -> None:
        target = (WEB_DIR / relative).resolve()
        if not str(target).startswith(str(WEB_DIR.resolve())) or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        mime, _ = mimetypes.guess_type(target.name)
        self.send_response(200)
        self.send_header("Content-Type", (mime or "application/octet-stream") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/accounts":
            filters = {
                "minPrice": _num(query.get("minPrice", [None])[0]),
                "maxPrice": _num(query.get("maxPrice", [None])[0]),
                "minSpeed": _num(query.get("minSpeed", [None])[0]),
                "minLucky": _num(query.get("minLucky", [None])[0]),
                "minHead": _num(query.get("minHead", [None])[0]),
                "minTail": _num(query.get("minTail", [None])[0]),
                "minPvp": _num(query.get("minPvp", [None])[0]),
                "minSixStar": _num(query.get("minSixStar", [None])[0]),
                "minFengzidu": _num(query.get("minFengzidu", [None])[0]),
                "minPanel": _num(query.get("minPanel", [None])[0]),
                "panelSuit": query.get("panelSuit", ["狂骨"])[0],
                "area": query.get("area", [""])[0],
                "keyword": query.get("keyword", [""])[0],
                "tag": query.get("tag", [""])[0],
            }
            sort = query.get("sort", ["speed"])[0]
            desc = query.get("desc", ["1"])[0] != "0"
            limit = min(int(_num(query.get("limit", ["60"])[0]) or 60), 300)
            offset = int(_num(query.get("offset", ["0"])[0]) or 0)
            conn = store.connect()
            try:
                payload = store.query(conn, filters, sort=sort, desc=desc, limit=limit, offset=offset)
            finally:
                conn.close()
            self._json(payload)
            return

        if path.startswith("/api/account/"):
            eid = urllib.parse.unquote(path.rsplit("/", 1)[-1])
            conn = store.connect()
            try:
                listing = store.get_listing(conn, eid)
                metrics = store.get_metrics(conn, eid)
            finally:
                conn.close()
            if not listing:
                self._json({"error": "not found"}, 404)
                return
            self._json({"listing": listing, "metrics": metrics})
            return

        if path == "/api/stats":
            conn = store.connect()
            try:
                payload = store.stats(conn)
            finally:
                conn.close()
            payload["thresholds"] = THRESHOLDS
            payload["fourPieceSuits"] = FOUR_PIECE_SUITS
            self._json(payload)
            return

        if path in ("/", "/index.html"):
            self._file("index.html")
            return

        self._file(path.lstrip("/"))

    def log_message(self, fmt: str, *args) -> None:
        pass


def serve() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"筛选器已启动： http://{HOST}:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("已停止")
