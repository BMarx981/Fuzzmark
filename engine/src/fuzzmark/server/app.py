"""HTTP transport for the local engine API.

Thin adapter around `routes.dispatch`: parse JSON, dispatch, serialize
the result. Long-running operations don't block a single request — the
client `POST`s `/api/jobs/*` to start a background job (route returns a
`job_id` immediately) and `GET`s `/api/jobs/{id}/events` to stream
Server-Sent Events as the job progresses.

Uses stdlib `http.server` so no new runtime dependency is added. Binds
to 127.0.0.1 by default — this server is intentionally a local IPC
channel for the desktop app, not an exposed service.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Tuple

from ..jobs import get_job
from .routes import RouteError, dispatch, parse_job_events_path


log = logging.getLogger(__name__)


_SSE_KEEPALIVE_SECONDS = 15.0


class _Handler(BaseHTTPRequestHandler):
    server_version = "Fuzzmark/0.1"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        log.info("%s - - %s", self.address_string(), format % args)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._write_status(204)
        self._write_cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        # SSE event streams are GET-only.
        sse_job_id = parse_job_events_path(self.path)
        if sse_job_id is not None:
            self._handle_sse(sse_job_id)
            return
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")

    def _handle(self, method: str) -> None:
        payload = self._read_payload()
        if payload is None:
            return
        try:
            body = dispatch(method, self.path, payload)
            self._respond(200, body)
        except RouteError as err:
            if err.status >= 500:
                log.exception(
                    "RouteError(%s) in %s %s: %s",
                    err.status,
                    method,
                    self.path,
                    err.message,
                )
            self._respond(err.status, {"error": err.message})
        except Exception as exc:  # noqa: BLE001
            log.exception("unhandled error in %s %s", method, self.path)
            self._respond(500, {"error": f"internal error: {exc.__class__.__name__}"})

    def _handle_sse(self, job_id: str) -> None:
        """Stream a job's event log as Server-Sent Events until terminal."""
        job = get_job(job_id)
        if job is None:
            self._respond(404, {"error": f"job not found: {job_id}"})
            return
        self._write_sse_headers()
        try:
            for event in job.stream(keepalive_interval=_SSE_KEEPALIVE_SECONDS):
                if event is None:
                    self._write_sse_comment()
                else:
                    self._write_sse_event(event)
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client disconnected mid-stream. The job keeps running; another
            # SSE consumer can subscribe and replay from the start.
            return

    def _read_payload(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._respond(400, {"error": f"invalid JSON body: {exc}"})
            return None
        if not isinstance(payload, dict):
            self._respond(400, {"error": "request body must be a JSON object"})
            return None
        return payload

    def _respond(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self._write_status(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._write_cors()
        self.end_headers()
        self.wfile.write(data)

    def _write_sse_headers(self) -> None:
        # Close the TCP socket when the stream ends so the client sees EOF
        # immediately after the terminal SSE event — otherwise the kept-alive
        # connection would block the client's reader until socket timeout.
        self.close_connection = True
        self._write_status(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")  # disable proxy buffering
        self._write_cors()
        self.end_headers()

    def _write_sse_event(self, event: dict) -> None:
        data = json.dumps(event, ensure_ascii=False)
        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _write_sse_comment(self) -> None:
        # SSE comment line — clients ignore but proxies see traffic.
        self.wfile.write(b": keepalive\n\n")
        self.wfile.flush()

    def _write_status(self, code: int) -> None:
        self.send_response(code)

    def _write_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Construct a configured ThreadingHTTPServer; caller owns its lifecycle."""
    return ThreadingHTTPServer((host, port), _Handler)


def serve_forever(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Block, serving the API on host:port until the process is interrupted."""
    server = make_server(host, port)
    bound_host, bound_port = server.server_address[:2]
    log.info("fuzzmark serve listening on http://%s:%s", bound_host, bound_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def bound_address(server: ThreadingHTTPServer) -> Tuple[str, int]:
    """Return (host, port) the server is actually bound to (port 0 → resolved)."""
    host, port = server.server_address[:2]
    return str(host), int(port)
