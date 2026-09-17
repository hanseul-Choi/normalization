"""Lightweight HTTP REST API daemon using Python standard library (`docs/10-api-design.md`, `docs/13-roadmap.md`)."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import secnorm
from secnorm.pipeline import PIPELINE_VERSION


class SecnormRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler providing REST endpoints for secnorm."""

    server_version = f"secnorm/{PIPELINE_VERSION}"

    def _send_json(self, status: int, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {
                "status": "ok",
                "version": PIPELINE_VERSION,
            })
        else:
            self._send_error(404, f"Endpoint {self.path} not found")

    def do_POST(self) -> None:
        content_length_str = self.headers.get("Content-Length")
        if not content_length_str:
            self._send_error(400, "Missing Content-Length header")
            return

        try:
            content_length = int(content_length_str)
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            self._send_error(400, f"Malformed JSON request body: {e}")
            return

        if self.path == "/normalize":
            text = payload.get("text")
            if text is None or not isinstance(text, str):
                self._send_error(400, "'text' field is required and must be a string")
                return

            preset = payload.get("preset", "security_balanced")
            include_raw_text = payload.get("include_raw_text", True)

            try:
                result = secnorm.normalize(text, preset=preset)
                self._send_json(200, result.to_dict(include_raw_text=include_raw_text))
            except ValueError as e:
                self._send_error(400, str(e))

        elif self.path == "/normalize/batch":
            texts = payload.get("texts")
            if texts is None or not isinstance(texts, list):
                self._send_error(400, "'texts' field is required and must be a list of strings")
                return

            preset = payload.get("preset", "security_balanced")
            include_raw_text = payload.get("include_raw_text", True)
            n_jobs = payload.get("n_jobs", 1)

            try:
                results = secnorm.normalize_batch(texts, preset=preset, n_jobs=n_jobs)
                data = [r.to_dict(include_raw_text=include_raw_text) for r in results]
                self._send_json(200, data)
            except ValueError as e:
                self._send_error(400, str(e))

        else:
            self._send_error(404, f"Endpoint {self.path} not found")

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard request logs during testing unless needed
        sys.stderr.write(f"[secnorm-server] {self.address_string()} - {format % args}\n")


def create_server(host: str = "127.0.0.1", port: int = 8000) -> HTTPServer:
    """Create and return configured HTTPServer instance."""
    return HTTPServer((host, port), SecnormRequestHandler)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start blocking HTTP server on host:port."""
    server = create_server(host, port)
    print(f"Starting secnorm HTTP server on http://{host}:{port} ...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start secnorm lightweight HTTP daemon.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1).")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Port to listen on (default: 8000).")
    args = parser.parse_args(argv)

    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
