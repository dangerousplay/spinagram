"""``spinagram serve``: Starlette app (JSON API + SSE + the built SPA) and the file watcher."""
from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import themes
from .catalog import FetchConflict, Offline, PackService
from .events import EventBus
from .workspace import RenderError, Workspace

STATIC = Path(__file__).parent / "static"
HOSTS = ["127.0.0.1", "localhost"]
NO_STORE = {"Cache-Control": "no-store"}

PLACEHOLDER = """<!doctype html><meta charset="utf-8"><title>spinagram</title>
<body style="font-family:system-ui;padding:40px">The web bundle is not built.
Run <code>bun install && bun run build</code> in <code>web/</code> (or use <code>bun run dev</code>).
The API is up at <a href="/api/workspace">/api/workspace</a>.</body>"""


def _err(status: int, message: str, **extra) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status, headers=NO_STORE)


def create_app(ws: Workspace, bus: EventBus | None = None, packs: PackService | None = None,
               watch: bool = True) -> Starlette:
    bus = bus or EventBus()

    def on_pack(event: dict) -> None:
        bus.publish(event)
        if event.get("status") == "done":  # icons of the new pack can now appear in diagrams
            ws.reload_theme()  # a fresh Theme forgets icons it resolved as missing
            bus.publish({"type": "diagram", "keys": ws.all_keys()})

    packs = packs or PackService(on_pack)

    async def workspace(_: Request) -> Response:
        return JSONResponse(await run_in_threadpool(ws.summary), headers=NO_STORE)

    async def diagram(req: Request) -> Response:
        key = req.path_params["key"]
        try:
            svg, info = await run_in_threadpool(ws.render, key, req.query_params.get("layout") or None)
        except KeyError:
            return _err(404, f"unknown diagram {key}")
        except RenderError as exc:
            return _err(422, str(exc), file=exc.file)
        meta = quote(json.dumps({**info, "overflow": list(info["overflow"]) if info.get("overflow") else None}))
        return Response(svg, media_type="image/svg+xml", headers={**NO_STORE, "X-Diagram-Info": meta})

    async def styles(req: Request) -> Response:
        key = req.path_params["key"]
        try:
            report = await run_in_threadpool(ws.styles, key, req.query_params.get("layout") or None)
        except KeyError:
            return _err(404, f"unknown diagram {key}")
        except RenderError as exc:
            return _err(422, str(exc), file=exc.file)
        return JSONResponse(report, headers=NO_STORE)

    async def theme_list(_: Request) -> Response:
        return JSONResponse(await run_in_threadpool(themes.list_themes, ws.theme_ref), headers=NO_STORE)

    async def theme_sheet(req: Request) -> Response:
        try:
            return JSONResponse(await run_in_threadpool(themes.theme_sheet, req.path_params["ref"], ws.theme_ref),
                                headers=NO_STORE)
        except KeyError as exc:
            return _err(404, f"unknown theme {exc}")
        except Exception as exc:  # noqa: BLE001 — broken theme file: show why
            return _err(422, str(exc))

    async def theme_preview(req: Request) -> Response:
        p = req.path_params
        try:
            svg = await run_in_threadpool(themes.style_preview, p["ref"], ws.theme_ref, p["kind"], p["style"])
        except KeyError:
            return _err(404, "unknown style")
        except Exception as exc:  # noqa: BLE001
            return _err(422, str(exc))
        return Response(svg, media_type="image/svg+xml", headers=NO_STORE)

    async def theme_font(req: Request) -> Response:
        p = req.path_params
        try:
            f = await run_in_threadpool(themes.font_file, p["ref"], ws.theme_ref, p["role"], p["key"])
        except Exception:  # noqa: BLE001
            return _err(404, "unknown font")
        return FileResponse(f)

    async def pack_list(_: Request) -> Response:
        return JSONResponse({"offline": packs.offline(), "packs": await run_in_threadpool(packs.list)},
                            headers=NO_STORE)

    async def pack_icons(req: Request) -> Response:
        try:
            return JSONResponse(await run_in_threadpool(packs.icons, req.path_params["name"]), headers=NO_STORE)
        except KeyError:
            return _err(404, "unknown pack")
        except LookupError as exc:
            return _err(409, str(exc))

    async def pack_icon(req: Request) -> Response:
        p = req.path_params
        try:
            f = await run_in_threadpool(packs.icon_file, p["name"], p["icon"], req.query_params.get("tone", "light"))
        except KeyError:
            return _err(404, "unknown icon")
        return FileResponse(f, headers={"Cache-Control": "max-age=3600"})

    async def pack_fetch(req: Request) -> Response:
        try:
            packs.start_fetch(req.path_params["name"])
        except KeyError:
            return _err(404, "unknown pack")
        except FetchConflict:
            return _err(409, "fetch already running")
        except Offline as exc:
            return _err(403, f"downloads disabled ({exc})")
        return JSONResponse({"status": "fetching"}, status_code=202)

    async def events(_: Request) -> Response:
        return StreamingResponse(bus.stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def placeholder(_: Request) -> Response:
        return HTMLResponse(PLACEHOLDER)

    routes = [
        Route("/api/workspace", workspace),
        Route("/api/diagrams/{key:path}.svg", diagram),
        Route("/api/diagrams/{key:path}.styles", styles),
        Route("/api/themes", theme_list),
        Route("/api/themes/{ref}", theme_sheet),
        Route("/api/themes/{ref}/preview/{kind}/{style}.svg", theme_preview),
        Route("/api/themes/{ref}/font/{role}/{key}", theme_font),
        Route("/api/packs", pack_list),
        Route("/api/packs/{name}/icons", pack_icons),
        Route("/api/packs/{name}/icons/{icon}", pack_icon),
        Route("/api/packs/{name}/fetch", pack_fetch, methods=["POST"]),
        Route("/api/events", events),
    ]
    if (STATIC / "index.html").is_file():
        routes.append(Mount("/", StaticFiles(directory=STATIC, html=True)))
    else:
        routes.append(Route("/", placeholder))

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        bus.bind(asyncio.get_running_loop())
        stop = asyncio.Event()
        task = asyncio.create_task(watch_loop(ws, bus, stop)) if watch else None
        try:
            yield
        finally:
            stop.set()
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            packs.shutdown()

    return Starlette(routes=routes, lifespan=lifespan,
                     middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=HOSTS)])


# watcher ------------------------------------------------------------------------------------------
def classify(ws: Workspace, roots: list[Path], paths: set[Path]) -> tuple[bool, list[Path]]:
    """(theme changed, spec-side files changed) for a batch of changed paths."""
    theme_hit, spec = False, []
    spec_dirs = ws.spec_dirs()
    for p in paths:
        if any(p.is_relative_to(r) for r in roots):
            theme_hit = True
        elif p.parent in spec_dirs and (p.suffix in {".yaml", ".yml", ".py"}):
            spec.append(p)
    return theme_hit, spec


def apply_changes(ws: Workspace, roots: list[Path], paths: set[Path]) -> list[dict]:
    """Reload what a batch of changes touches; returns the events to publish (sync, for a thread)."""
    theme_hit, spec = classify(ws, roots, paths)
    out: list[dict] = []
    if theme_hit:
        ws.reload_theme()
        out.append({"type": "theme", "ref": "active"})
    if spec or theme_hit:
        rescanned = ws.rescan()
        keys = ws.all_keys() if theme_hit else (ws.reload_files(spec) if spec else [])
        if rescanned or keys:
            out.append({"type": "workspace"})  # titles, errors and the file list may have changed
        if keys:
            out.append({"type": "diagram", "keys": keys})
    return out


async def watch_loop(ws: Workspace, bus: EventBus, stop: asyncio.Event) -> None:
    from watchfiles import awatch

    while not stop.is_set():
        roots = await run_in_threadpool(ws.theme_roots)
        targets = sorted({str(d) for d in ws.spec_dirs()} | {str(r) for r in roots})
        async for changes in awatch(*targets, stop_event=stop, debounce=150, step=50):
            paths = {Path(p).resolve() for _, p in changes}
            for event in await run_in_threadpool(apply_changes, ws, roots, paths):
                bus.publish(event)
            if await run_in_threadpool(ws.theme_roots) != roots:
                break  # `extends` changed: watch the new chain


# entry point --------------------------------------------------------------------------------------
def run(paths: list[str], *, theme: str | None = None, layout: str | None = None, port: int = 8765,
        open_browser: bool = True) -> int:
    import uvicorn

    from .. import icons

    icons.AUTO_FETCH = False  # never download inside a render: missing packs are fetched from the UI
    ws = Workspace(paths, theme, layout)
    app = create_app(ws)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError as exc:
        print(f"spinagram: port {port} unavailable ({exc.strerror}); try --port 0", file=sys.stderr)
        return 2
    url = f"http://127.0.0.1:{sock.getsockname()[1]}/"
    n = len(ws.all_keys())
    print(f"spinagram serve: {n} diagram(s) from {', '.join(map(str, ws.paths))} · theme {ws.theme_ref or 'default'}")
    print(f"  {url}  (Ctrl+C to stop)", flush=True)
    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    server.run(sockets=[sock])
    return 0
