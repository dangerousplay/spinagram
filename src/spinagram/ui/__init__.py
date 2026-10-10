"""Live-reload web UI (``spinagram serve``): needs the ``ui`` extra (starlette, uvicorn, watchfiles).

``workspace``, ``themes`` and ``catalog`` are plain Python (no web imports) so they are testable alone;
``server`` wires them to HTTP and server-sent events.
"""
