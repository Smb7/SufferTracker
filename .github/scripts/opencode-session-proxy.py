#!/usr/bin/env python3
"""Forward SquidGate LLM calls to OpenCode Go with a stable session header.

OpenCode Go rejects requests that omit x-opencode-session. SquidGate's action
does not send custom headers, so the workflow points it at this local proxy.
"""

from __future__ import annotations

import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request

UPSTREAM = os.environ.get("OPENCODE_UPSTREAM", "https://opencode.ai/zen/go/v1").rstrip("/")
SESSION = os.environ.get("OPENCODE_SESSION") or f"squidgate-{uuid.uuid4()}"
HOST = "127.0.0.1"
PORT = int(os.environ.get("OPENCODE_PROXY_PORT", "8765"))
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade", "content-length"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/healthz":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._forward()

    def do_POST(self) -> None:
        self._forward()

    def _forward(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else None
        path = self.path
        if path == "/v1" or path.startswith("/v1/") or path.startswith("/v1?"):
            path = path[3:] or "/"
        upstream = f"{UPSTREAM}{path}"
        headers = {
            "Content-Type": self.headers.get("Content-Type", "application/json"),
            "x-opencode-session": SESSION,
            "User-Agent": "SufferTracker-SquidGate/1.0",
        }
        authorization = self.headers.get("Authorization")
        if authorization:
            headers["Authorization"] = authorization
        api_key = self.headers.get("api-key")
        if api_key:
            headers["api-key"] = api_key
        outbound = request.Request(upstream, data=body, headers=headers, method=self.command)
        try:
            with request.urlopen(outbound, timeout=180) as response:
                payload = response.read()
                status = response.status
                response_headers = response.headers
        except error.HTTPError as exc:
            payload = exc.read()
            status = exc.code
            response_headers = exc.headers
        self.send_response(status)
        content_type = response_headers.get("Content-Type")
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        # Avoid writing request headers, which include the LLM credential.
        print(f"{self.address_string()} {self.command} {self.path}")


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
