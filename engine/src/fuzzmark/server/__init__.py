"""Local HTTP API exposing the engine to the Flutter desktop frontend.

The transport (`app.py`) is stdlib-only; the routes pull in `scanner.crawl`
when a scan is requested, which is the one path that needs Playwright at
runtime — every other route stays browser-free. The Flutter app talks to
this server over HTTP on 127.0.0.1 by default. A WebSocket progress
channel for long-running runs will land alongside the Run view.
"""

from .app import make_server, serve_forever
from .routes import RouteError, dispatch

__all__ = ["RouteError", "dispatch", "make_server", "serve_forever"]
