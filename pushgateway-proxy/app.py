#!/usr/bin/env python3
"""
Proxy in front of Pushgateway: converts PUT to POST so clients that use PUT can push metrics.
Pushgateway only supports POST for push; GET and DELETE are passed through as-is.
"""
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error


LISTEN_PORT = int(os.environ.get("PORT", "9091"))
PUSHGATEWAY_HOST = os.environ.get("PUSHGATEWAY_HOST", "pushgateway")
PUSHGATEWAY_PORT = int(os.environ.get("PUSHGATEWAY_PORT", "9091"))


def forward(method: str, path: str, body: bytes, headers: dict) -> tuple[int, dict, bytes]:
    """Forward request to Pushgateway. Use POST when method is PUT."""
    out_method = "POST" if method == "PUT" else method
    url = f"http://{PUSHGATEWAY_HOST}:{PUSHGATEWAY_PORT}{path}"
    req_headers = {k: v for k, v in headers.items() if k.lower() not in ("host", "connection")}
    req = urllib.request.Request(url, data=body if body else None, headers=req_headers, method=out_method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except urllib.error.URLError as e:
        raise RuntimeError(str(e.reason))


class ProxyHandler(BaseHTTPRequestHandler):
    def do_REQUEST(self, method: str):
        path = self.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""
        headers = {k: v for k, v in self.headers.items()}

        try:
            status, out_headers, out_body = forward(method, path, body, headers)
        except Exception as e:
            self.send_error(502, f"Pushgateway unreachable: {e}")
            return

        self.send_response(status)
        for k, v in out_headers.items():
            if k.lower() not in ("transfer-encoding", "connection"):
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(out_body)

    def do_GET(self):
        self.do_REQUEST("GET")

    def do_POST(self):
        self.do_REQUEST("POST")

    def do_PUT(self):
        self.do_REQUEST("PUT")

    def do_DELETE(self):
        self.do_REQUEST("DELETE")

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}", flush=True)


def main():
    server = HTTPServer(("", LISTEN_PORT), ProxyHandler)
    print(f"Pushgateway proxy listening on {LISTEN_PORT} (PUT→POST to {PUSHGATEWAY_HOST}:{PUSHGATEWAY_PORT})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
