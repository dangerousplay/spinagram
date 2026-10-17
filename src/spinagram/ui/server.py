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

from . import files as fsx
from . import themes
from .catalog import FetchConflict, Offline, PackService
from .events import EventBus
from .workspace import RenderError, VersionConflict, Workspace

STATIC = Path(__file__).parent / "static"
HOSTS = ["127.0.0.1", "localhost"]
NO_STORE = {"Cache-Control": "no-store"}
GUARD = "X-Spinagram"  # required on source, write and folder routes: other origins cannot send it (no CORS)
MAX_SAVE = 1024 * 1024  # bytes of request body a save may carry

PLACEHOLDER = """<!doctype html><meta charset="utf-8"><title>spinagram</title>
<body style="font-family:system-ui;padding:40px">The web bundle is not built.
Run <code>bun install && bun run build</code> in <code>web/</code> (or use <code>bun run dev</code>).
The API is up at <a href="/api/workspace">/api/workspace</a>.</body>"""


def _err(status: int, message: str, **extra) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status, headers=NO_STORE)


def _guard(req: Request) -> Response | None:
    """403 unless the request carries ``X-Spinagram: 1`` (sent by the UI; a cross-site page cannot send it)."""
    return None if req.headers.get(GUARD) == "1" else _err(403, f"missing {GUARD} header")


def create_app(ws: Workspace, bus: EventBus | None = None, packs: PackService | None = None,
               watch: bool = True) -> Starlette:
    bus = bus or EventBus()

    def on_pack(event: dict) -> None:
        bus.publish(event)
        if event.get("status") == "done":  # icons of the new pack can now appear in diagrams
            ws.reload_theme()  # a fresh Theme forgets icons it resolved as missing
            bus.publish({"type": "diagram", "keys": ws.all_keys()})

    packs = packs or PackService(on_pack)
    retarget = asyncio.Event()  # set when the workspace root changes: the watcher restarts on the new folders

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

    async def source(req: Request) -> Response:
        if (denied := _guard(req)) is not None:
            return denied
        key = req.path_params["key"]
        try:
            return JSONResponse({"files": await run_in_threadpool(ws.source, key)}, headers=NO_STORE)
        except KeyError:
            return _err(404, f"unknown diagram {key}")
        except FileNotFoundError as exc:
            return _err(404, f"file removed: {exc.filename}")

    async def save(req: Request) -> Response:
        if (denied := _guard(req)) is not None:
            return denied
        body = await req.body()
        if len(body) > MAX_SAVE:
            return _err(413, f"file too large: the limit is {MAX_SAVE} bytes")
        try:
            data = json.loads(body.decode("utf-8"))
        except UnicodeDecodeError:
            return _err(422, "the text is not valid UTF-8")
        except ValueError:
            return _err(422, "the body is not JSON")
        if not isinstance(data, dict) or not all(isinstance(data.get(k), str) for k in ("path", "text", "version")):
            return _err(422, "expected {path, text, version}")
        try:
            data["text"].encode("utf-8")  # JSON escapes can carry lone surrogates, which no file can hold
        except UnicodeEncodeError:
            return _err(422, "the text is not valid UTF-8")
        try:
            version = await run_in_threadpool(ws.write, data["path"], data["text"], data["version"])
        except PermissionError as exc:
            return _err(403, str(exc))
        except VersionConflict as exc:
            return _err(409, str(exc), version=exc.current)
        except FileNotFoundError:
            return _err(404, f"file removed: {data['path']}")
        return JSONResponse({"version": version}, headers=NO_STORE)

    async def list_dir(req: Request) -> Response:
        if (denied := _guard(req)) is not None:
            return denied
        path = req.query_params.get("path") or str(next((p for p in ws.paths if p.is_dir()), ws.paths[0].parent))
        try:
            return JSONResponse(await run_in_threadpool(fsx.list_dir, path), headers=NO_STORE)
        except NotADirectoryError as exc:
            return _err(404, str(exc))
        except PermissionError as exc:
            return _err(403, f"cannot read {exc.filename or path}")

    async def open_folder(req: Request) -> Response:
        if (denied := _guard(req)) is not None:
            return denied
        try:
            data = await req.json()
        except ValueError:
            return _err(422, "the body is not JSON")
        if not isinstance(data, dict) or not isinstance(data.get("path"), str):
            return _err(422, "expected {path}")
        try:
            await run_in_threadpool(ws.open, data["path"])
        except NotADirectoryError as exc:
            return _err(404, str(exc))
        except PermissionError as exc:
            return _err(403, f"cannot read {exc.filename or data['path']}")
        retarget.set()
        bus.publish({"type": "workspace"})
        return JSONResponse(await run_in_threadpool(ws.summary), headers=NO_STORE)

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

    async def theme_thumbnail(req: Request) -> Response:
        try:
            svg = await run_in_threadpool(themes.theme_thumbnail, req.path_params["ref"], ws.theme_ref)
        except KeyError as exc:
            return _err(404, f"unknown theme {exc}")
        except Exception as exc:  # noqa: BLE001 — broken theme file: show why
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
        Route("/api/workspace/open", open_folder, methods=["POST"]),
        Route("/api/fs", list_dir),
        Route("/api/diagrams/{key:path}.svg", diagram),
        Route("/api/diagrams/{key:path}.styles", styles),
        Route("/api/diagrams/{key:path}.source", source),
        Route("/api/files", save, methods=["PUT"]),
        Route("/api/themes", theme_list),
        Route("/api/themes/{ref}", theme_sheet),
        Route("/api/themes/{ref}/thumbnail.svg", theme_thumbnail),
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
        task = asyncio.create_task(watch_loop(ws, bus, stop, retarget)) if watch else None
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
def classify(ws: Workspace, roots: list[Path], paths: set[Path]) -> tuple[bool, list[Path], list[Path]]:
    """(theme changed, spec-side files changed, stylesheets changed) for a batch of changed paths.
    A theme's ``theme.css`` counts as a theme change."""
    theme_hit, spec, sheets = False, [], []
    for p in paths:
        if any(p.is_relative_to(r) for r in roots):
            theme_hit = True
        elif p.suffix == ".css":
            sheets.append(p)
        elif p.suffix in fsx.SPEC_EXTS and ws.contains(p):  # any depth under an open root
            spec.append(p)
    return theme_hit, spec, sheets


def apply_changes(ws: Workspace, roots: list[Path], paths: set[Path]) -> list[dict]:
    """Reload what a batch of changes touches; returns the events to publish (sync, for a thread)."""
    theme_hit, spec, sheets = classify(ws, roots, paths)
    out: list[dict] = []
    if theme_hit:
        ws.reload_theme()
        out.append({"type": "theme", "ref": "active"})
    keys: list[str] = []
    if spec or theme_hit:
        rescanned = ws.rescan()
        keys = ws.all_keys() if theme_hit else (ws.reload_files(spec) if spec else [])
        if rescanned or keys:
            out.append({"type": "workspace"})  # titles, errors and the file list may have changed
    if sheets and not theme_hit:
        keys = sorted(set(keys) | set(ws.stylesheets_changed(sheets)))
    if keys:
        out.append({"type": "diagram", "keys": keys})
    return out


async def watch_loop(ws: Workspace, bus: EventBus, stop: asyncio.Event,
                     retarget: asyncio.Event | None = None) -> None:
    from watchfiles import awatch

    retarget = retarget or asyncio.Event()
    while not stop.is_set():
        roots = await run_in_threadpool(ws.theme_roots)
        dirs = await run_in_threadpool(ws.watch_dirs, roots)
        targets = sorted(str(d) for d in dirs)
        done = asyncio.Event()  # ends this round: server stop or a new workspace root

        async def relay() -> None:
            waits = [asyncio.ensure_future(stop.wait()), asyncio.ensure_future(retarget.wait())]
            try:
                await asyncio.wait(waits, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for w in waits:
                    w.cancel()
            done.set()

        relay_task = asyncio.create_task(relay())
        try:
            async for changes in awatch(*targets, stop_event=done, debounce=150, step=50):
                paths = {Path(p).resolve() for _, p in changes}
                for event in await run_in_threadpool(apply_changes, ws, roots, paths):
                    bus.publish(event)
                new_roots = await run_in_threadpool(ws.theme_roots)
                if new_roots != roots or await run_in_threadpool(ws.watch_dirs, new_roots) != dirs:
                    break  # `extends` or the referenced stylesheet folders changed: watch the new set
        finally:
            relay_task.cancel()
        retarget.clear()


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
