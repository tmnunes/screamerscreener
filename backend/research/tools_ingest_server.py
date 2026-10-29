"""Local ingest endpoint used when agent/browser downloads Binance vision zips.

POST JSON: {kind, symbol, year, month, interval?, b64}
Writes extracted CSV under data/research/raw/.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data" / "research" / "raw"


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true,"service":"research-ingest"}')

    def do_POST(self) -> None:  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n))
        kind = body["kind"]
        symbol = body["symbol"]
        year = int(body["year"])
        month = int(body["month"])
        interval = body.get("interval")
        raw = base64.b64decode(body["b64"])
        if kind == "klines":
            dest_dir = ROOT / "klines" / symbol / interval
            dest = dest_dir / f"{symbol}-{interval}-{year:04d}-{month:02d}.csv"
        else:
            dest_dir = ROOT / "funding" / symbol
            dest = dest_dir / f"{symbol}-fundingRate-{year:04d}-{month:02d}.csv"
        dest_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".csv"))
            dest.write_bytes(zf.read(name))
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {"ok": True, "path": str(dest), "bytes": dest.stat().st_size}
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        print(f"[ingest] {args[1]} {args[0]}")


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    server = HTTPServer(("127.0.0.1", 8765), Handler)
    print(f"ingest listening on http://127.0.0.1:8765 root={ROOT}", flush=True)
    server.serve_forever()
