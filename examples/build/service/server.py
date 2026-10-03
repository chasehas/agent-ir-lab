"""Internal "orders" service for the worked examples. GET /health returns status JSON.

Each request is written to /logs/access.log in Apache combined format, in the
service's local time (TZ, US Eastern by default).
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

LOG_PATH = os.environ.get("ACCESS_LOG", "/logs/access.log")
TZ = ZoneInfo(os.environ.get("TZ", "America/New_York"))
HEALTH = {"service": "orders", "status": "ok", "version": "2.3.1", "queue_depth": 14}


class Handler(BaseHTTPRequestHandler):
    server_version = "orders/2.3.1"
    sys_version = ""

    def do_GET(self):
        status, body = (200, HEALTH) if self.path == "/health" else (404, {"error": "not found"})
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        now = datetime.now(TZ).strftime("%d/%b/%Y:%H:%M:%S %z")
        with open(LOG_PATH, "a") as f:
            f.write(
                f'{self.client_address[0]} - - [{now}] "{self.requestline}" {status} {len(payload)} '
                f'"-" "{self.headers.get("User-Agent", "-")}"\n'
            )

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
