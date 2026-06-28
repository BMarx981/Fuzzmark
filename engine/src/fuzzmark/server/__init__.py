"""Local HTTP API exposing the engine to the Flutter desktop frontend.

Stdlib-only — kept browser-free and dependency-free so it can be imported and
exercised in pure-Python tests. The Flutter app talks to it over HTTP on
127.0.0.1 by default. Long-running operations (scan, run) will land later
with a WebSocket progress channel; this first slice only exposes the
synchronous project endpoints needed by the Projects/home screen.
"""

from .app import make_server, serve_forever
from .routes import RouteError, dispatch

__all__ = ["RouteError", "dispatch", "make_server", "serve_forever"]
