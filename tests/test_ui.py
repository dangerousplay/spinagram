"""Live UI (spec: .specs/features/live-ui) — workspace, theme sheets, packs and the HTTP API."""
from __future__ import annotations

import asyncio
import time

import pytest

pytest.importorskip("starlette")
from starlette.testclient import TestClient  # noqa: E402

from spinagram.ui import themes  # noqa: E402
from spinagram.ui.catalog import PackService  # noqa: E402
from spinagram.ui.events import EventBus  # noqa: E402
from spinagram.ui.server import apply_changes, create_app  # noqa: E402
from spinagram.ui.workspace import Workspace  # noqa: E402

SVG_DOT = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><circle r="4"/></svg>'
BOX = "id: {id}\ntitle: {title}\nnodes:\n  - {{id: a, x: 100, y: 200, w: 300, h: 120, title: A}}\n"
AUTO = ("id: AU\ntitle: auto\nlayout: {engine: flex}\nnodes:\n  - {id: a, title: A}\n  - {id: b, title: B}\n"
        "edges: [a -> b]\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SPINAGRAM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("SPINAGRAM_OFFLINE", raising=False)
    monkeypatch.chdir(tmp_path)
    from spinagram import icons

    icons._INDEX_CACHE.clear()
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "one.yaml").write_text(BOX.format(id="D1", title="First"))
    (specs / "auto.yaml").write_text(AUTO)
    return tmp_path


def client(ws: Workspace, **kw) -> TestClient:
    return TestClient(create_app(ws, watch=False, **kw), base_url="http://127.0.0.1")


# workspace ----------------------------------------------------------------------------------------
def test_workspace_lists_and_renders(env):
    ws = Workspace([env / "specs"])
    s = ws.summary()
    assert [f["path"] for f in s["files"]] == ["auto.yaml", "one.yaml"]
    assert s["files"][1]["diagrams"] == [{"key": "one.yaml#D1", "id": "D1", "title": "First", "auto": False}]
    assert {e["name"] for e in s["engines"]} >= {"flex"}
    svg, info = ws.render("one.yaml#D1")
    assert svg.startswith("<svg") and "First" in svg and info["overflow"] is None


def test_workspace_reload_error_and_recovery(env):
    ws = Workspace([env / "specs"])
    f = env / "specs" / "one.yaml"
    f.write_text("id: D1\ntitle: [broken\n")
    events = apply_changes(ws, ws.theme_roots(), {f})
    assert {"type": "diagram", "keys": ["one.yaml#D1"]} in events
    assert "invalid YAML" in ws.summary()["files"][1]["error"]
    f.write_text(BOX.format(id="D1", title="Second"))
    apply_changes(ws, ws.theme_roots(), {f})
    assert "Second" in ws.render("one.yaml#D1")[0]


def test_workspace_new_file_and_python_helper_reload(env):
    ws = Workspace([env / "specs"])
    (env / "specs" / "_helpers.py").write_text("TITLE = 'old'\n")
    spec = env / "specs" / "py.py"
    spec.write_text("from _helpers import TITLE\nfrom spinagram import Diagram\n"
                    "diagram = Diagram('P1', TITLE)\ndiagram.box('x', x=100, y=200, w=300, h=120)\n")
    events = apply_changes(ws, ws.theme_roots(), {spec})
    assert {"type": "workspace"} in events and "old" in ws.render("py.py#P1")[0]
    (env / "specs" / "_helpers.py").write_text("TITLE = 'new'\n")
    apply_changes(ws, ws.theme_roots(), {env / "specs" / "_helpers.py"})
    assert "new" in ws.render("py.py#P1")[0]


def test_layout_override_only_for_auto_diagrams(env):
    ws = Workspace([env / "specs"], layout="nope")
    with pytest.raises(Exception, match="nope"):
        ws.render("auto.yaml#AU")
    assert ws.render("one.yaml#D1")[0]  # explicit coordinates ignore the engine
    assert ws.render("auto.yaml#AU", "flex")[0]


def test_theme_change_rerenders_everything(env):
    theme = env / "theme"
    theme.mkdir()
    (theme / "theme.yaml").write_text("name: t\nextends: default\ncolors: {primary: '#FF0000'}\n")
    ws = Workspace([env / "specs"], theme=str(theme))
    assert ws.theme_roots()[0] == theme.resolve()
    (theme / "theme.yaml").write_text("name: t\nextends: default\ncolors: {primary: '#00FF00'}\n")
    events = apply_changes(ws, ws.theme_roots(), {(theme / "theme.yaml").resolve()})
    assert events[0] == {"type": "theme", "ref": "active"}
    assert sorted(next(e for e in events if e["type"] == "diagram")["keys"]) == ["auto.yaml#AU", "one.yaml#D1"]
    assert "#00FF00" in ws.render("one.yaml#D1")[0]


# themes -------------------------------------------------------------------------------------------
def test_theme_sheet_and_previews():
    sheet = themes.theme_sheet("default", None)
    primary = next(c for c in sheet["colors"] if c["token"] == "primary")
    assert primary["hex"] == "#2563EB" and primary["via"] is None
    assert {f["role"] for f in sheet["fonts"]} >= {"heading", "body"}
    node = next(r for r in sheet["styles"]["node"] if r["name"] == "dark")
    assert node["preview"] and node["swatches"]["fill"].startswith("#")
    svg = themes.style_preview("default", None, "node", "dark")
    assert 'viewBox="180 280 380 170"' in svg
    with pytest.raises(KeyError):
        themes.style_preview("default", None, "node", "missing")
    with pytest.raises(KeyError):
        themes.theme_sheet("../../etc", None)


def test_theme_list_marks_active(env):
    theme = env / "theme"
    theme.mkdir()
    (theme / "theme.yaml").write_text("name: corp\nextends: default\ncolors: {brand: primary}\n")
    lst = themes.list_themes(str(theme))
    assert lst[0] == {"ref": "active", "name": "corp", "builtin": False, "active": True, "error": None}
    brand = next(c for c in themes.theme_sheet("active", str(theme))["colors"] if c["token"] == "brand")
    assert brand["via"] == "primary" and brand["hex"] == "#2563EB"


# packs --------------------------------------------------------------------------------------------
def _listing_pack(env):
    from spinagram import icons

    site = env / "site"
    site.mkdir()
    (site / "db.svg").write_text(SVG_DOT)
    (site / "index.html").write_text('<i data-p="db.svg"></i>')
    icons.register("site", {"type": "listing", "url": (site / "index.html").as_uri(),
                            "pattern": 'data-p="([^"]+)"', "version": "1"})


def _wait(pred, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def test_pack_service_fetch_list_icons(env):
    _listing_pack(env)
    events = []
    svc = PackService(events.append)
    row = next(p for p in svc.list() if p["name"] == "site")
    assert not row["fetched"] and row["source"] == "listing"
    svc.start_fetch("site")
    assert _wait(lambda: any(e.get("status") == "done" for e in events)), events
    row = next(p for p in svc.list() if p["name"] == "site")
    assert row["fetched"] and row["count"] == 1 and not row["fetching"]
    assert svc.icons("site") == [{"name": "db", "aliases": [], "tones": ["light"], "ext": "svg"}]
    assert svc.icon_file("site", "db").read_text() == SVG_DOT
    with pytest.raises(KeyError):
        svc.icon_file("site", "../index")


# HTTP ---------------------------------------------------------------------------------------------
def test_api_routes(env):
    _listing_pack(env)
    ws = Workspace([env / "specs"])
    with client(ws) as c:
        assert c.get("/api/workspace").json()["files"][1]["path"] == "one.yaml"
        r = c.get("/api/diagrams/one.yaml#D1.svg".replace("#", "%23"))
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
        assert c.get("/api/diagrams/nope.yaml%23X.svg").status_code == 404
        (env / "specs" / "one.yaml").write_text("id: D1\ntitle: [x\n")
        apply_changes(ws, ws.theme_roots(), {env / "specs" / "one.yaml"})
        r = c.get("/api/diagrams/one.yaml%23D1.svg")
        assert r.status_code == 422 and r.json()["file"] == "one.yaml"
        assert c.get("/api/themes").json()[0]["ref"] == "default"
        assert c.get("/api/themes/default").json()["name"] == "default"
        assert c.get("/api/themes/default/preview/zone/soft.svg").status_code == 200
        assert c.get("/api/themes/nope").status_code == 404
        assert c.get("/api/themes/default/font/body/400").status_code == 404  # default has no font files
        assert c.get("/", headers={"host": "evil.example"}).status_code == 400
        assert c.post("/api/packs/site/fetch").status_code == 202
        assert _wait(lambda: c.get("/api/packs").json()["packs"][-1]["fetched"]
                     if c.get("/api/packs").json()["packs"][-1]["name"] == "site" else
                     next(p for p in c.get("/api/packs").json()["packs"] if p["name"] == "site")["fetched"])
        assert c.get("/api/packs/site/icons").json()[0]["name"] == "db"
        assert c.get("/api/packs/site/icons/db").text == SVG_DOT
        assert c.post("/api/packs/nope/fetch").status_code == 404


def test_api_fetch_conflict_and_offline(env, monkeypatch):
    _listing_pack(env)
    svc = PackService()
    svc._jobs["site"] = None  # a fetch in flight
    with client(Workspace([env / "specs"]), packs=svc) as c:
        assert c.post("/api/packs/site/fetch").status_code == 409
        monkeypatch.setenv("SPINAGRAM_OFFLINE", "1")
        svc._jobs.clear()
        assert c.post("/api/packs/site/fetch").status_code == 403
        assert c.get("/api/packs").json()["offline"] is True


def test_event_bus_fanout():
    async def go():
        bus = EventBus()
        bus.bind(asyncio.get_running_loop())
        gen = bus.stream(keepalive=0.05)
        assert "hello" in await gen.__anext__()
        bus.publish({"type": "diagram", "keys": ["a#b"]})
        assert '"keys": ["a#b"]' in await gen.__anext__()
        assert (await gen.__anext__()).startswith(": keep-alive")
        await gen.aclose()
        assert bus.clients == 0

    asyncio.run(go())


def test_cli_serve_without_extra(monkeypatch, capsys):
    import sys

    from spinagram.cli import main

    monkeypatch.setitem(sys.modules, "spinagram.ui.server", None)
    assert main(["serve", "--no-open"]) == 2
    assert "spinagram[ui]" in capsys.readouterr().err


def test_missing_pack_reported_and_rerender_after_fetch(env, monkeypatch):
    from spinagram import icons

    _listing_pack(env)
    monkeypatch.setattr(icons, "AUTO_FETCH", False)
    (env / "specs" / "ic.yaml").write_text(
        "id: IC\ntitle: icons\nnodes:\n  - {id: a, x: 100, y: 200, w: 300, h: 120, title: A, icon: 'site:db'}\n")
    ws = Workspace([env / "specs"])
    svg, info = ws.render("ic.yaml#IC")
    assert info["missing_packs"] == ["site"] and any("site:db" in w for w in info["warnings"])
    assert not (env / "cache" / "site").exists()  # nothing downloaded during the render
    events = []
    bus = EventBus()
    bus.publish = events.append
    with client(ws, bus=bus) as c:
        assert c.post("/api/packs/site/fetch").status_code == 202
        assert _wait(lambda: any(e.get("type") == "diagram" for e in events)), events
        from urllib.parse import unquote
        import json

        r = c.get("/api/diagrams/ic.yaml%23IC.svg")
        info = json.loads(unquote(r.headers["X-Diagram-Info"]))
        assert info["missing_packs"] == [] and info["warnings"] == []  # the icon resolves now


def test_concurrent_fetch_of_one_pack_is_serialised(env):
    from concurrent.futures import ThreadPoolExecutor

    from spinagram import icons

    _listing_pack(env)
    pack = icons.registry()["site"]
    with ThreadPoolExecutor(4) as ex:
        dirs = list(ex.map(lambda _: icons.fetch(pack), range(4)))
    assert len(set(dirs)) == 1 and (dirs[0] / "index.json").exists() and not dirs[0].with_name("1.tmp").exists()
