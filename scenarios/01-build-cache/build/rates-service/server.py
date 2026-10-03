"""Minimal internal rates service for the lab scenario.

GET /v1/rates with a known bearer token returns a rate table. Every request is
written to /logs/access.log in Apache combined format, in the service's local
time zone (TZ, US Eastern by default), with the token's key ID appended.
Tokens themselves are never logged.
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

LOG_PATH = os.environ.get("ACCESS_LOG", "/logs/access.log")
TZ = ZoneInfo(os.environ.get("TZ", "America/New_York"))

# token -> key ID. The lab's token is deliberately fake.
TOKENS = {"rtok_EXAMPLE_7f3c9a1e2b4d": "ci-build-key-02"}

RATES = {
    "base": "USD",
    "as_of": "2026-09-29",
    "rates": {"USD": 1.0, "EUR": 0.9132, "GBP": 0.7811, "JPY": 148.62, "CAD": 1.3547},
}


class Handler(BaseHTTPRequestHandler):
    server_version = "kestrel-rates/1.4"
    sys_version = ""

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        key_id = TOKENS.get(token, "-")
        if self.path != "/v1/rates":
            status, body = 404, {"error": "not found"}
        elif key_id == "-":
            status, body = 401, {"error": "missing or invalid token"}
        else:
            status, body = 200, RATES
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self._access_log(status, len(payload), key_id)

    def _access_log(self, status, size, key_id):
        now = datetime.now(TZ).strftime("%d/%b/%Y:%H:%M:%S %z")
        line = (
            f'{self.client_address[0]} - - [{now}] "{self.requestline}" {status} {size} '
            f'"-" "{self.headers.get("User-Agent", "-")}" key_id={key_id}\n'
        )
        with open(LOG_PATH, "a") as f:
            f.write(line)

    def log_message(self, format, *args):  # silence default stderr logging
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
