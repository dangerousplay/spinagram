"""The MCP binding through an in-process client (spec: .specs/features/mcp-server/spec.md)."""
from __future__ import annotations

import json
import shutil
import threading
import time
from pathlib import Path

import anyio
import pytest

pytest.importorskip("mcp")

from mcp import Client  # noqa: E402

from spinagram import skills  # noqa: E402
from spinagram.mcp_server import server as srv  # noqa: E402
from spinagram.mcp_server.tools import Tools  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def root(tmp_path):
    for name in ("decision.yaml", "quickstart.yaml", "software_architecture.yaml"):
        shutil.copy(EXAMPLES / name, tmp_path / name)
    return tmp_path


def run(server, fn):
    async def go():
        async with Client(server) as c:
            return await fn(c)
    return anyio.run(go)


def call(server, tool, args):
    return run(server, lambda c: c.call_tool(tool, args))


def test_tools_listed(root):  # MCP-01
    names = run(srv.build(Tools(root)), lambda c: c.list_tools())
    assert sorted(t.name for t in names.tools) == ["check", "icons_search", "layout", "render", "styles"]


def test_render_returns_paths_and_previews_in_order(root, monkeypatch):  # MCP-02, MCP-03
    seen = []

    def fake(scenes):
        seen.extend(sc.id for sc in scenes)
        return [PNG + sc.id.encode() for sc in scenes]

    monkeypatch.setattr(srv, "png_previews", fake)
    many = root / "many.yaml"
    many.write_text("".join(f"- id: M{i}\n  title: Diagram {i}\n  nodes:\n    - {{id: a, title: A, x: 100, y: 200}}\n"
                            for i in range(5)), encoding="utf-8")
    r = call(srv.build(Tools(root)), "render", {"paths": ["many.yaml"], "formats": ["svg"]})
    assert not r.is_error
    text, *images = r.content
    body = json.loads(text.text)
    assert sorted(body["written"]) == sorted(f"out/{p.name}" for p in (root / "out").iterdir())
    assert "preview" not in body
    assert [i.mime_type for i in images] == ["image/png"] * 4
    import base64
    assert [base64.b64decode(i.data)[len(PNG):].decode() for i in images] == ["M0", "M1", "M2", "M3"]
    assert seen == ["M0", "M1", "M2", "M3"]                                 # the fifth is never rendered


def test_preview_with_the_real_png_backend(root):  # MCP-03 (real Chromium; CI has none)
    try:
        srv.png_previews([])
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch().close()
    except Exception:
        pytest.skip("Chromium for Playwright not installed")
    r = call(srv.build(Tools(root)), "render", {"paths": ["decision.yaml"], "formats": ["svg"]})
    images = [c for c in r.content if c.type == "image"]
    import base64
    assert len(images) == 1 and base64.b64decode(images[0].data).startswith(PNG)


def test_preview_needs_the_png_extra(root, monkeypatch):  # MCP-04
    def missing(scenes):
        raise ImportError("No module named 'playwright'")

    monkeypatch.setattr(srv, "png_previews", missing)
    r = call(srv.build(Tools(root)), "render", {"paths": ["decision.yaml"], "formats": ["svg"]})
    assert not r.is_error and len(r.content) == 1
    body = json.loads(r.content[0].text)
    assert body["preview"] == "preview needs spinagram[png]" and body["written"]


def test_preview_failure_is_a_note(root, monkeypatch):  # edge case: preview fails for another reason
    def broken(scenes):
        raise RuntimeError("Executable doesn't exist at /x/chrome\nrun playwright install")

    monkeypatch.setattr(srv, "png_previews", broken)
    r = call(srv.build(Tools(root)), "render", {"paths": ["decision.yaml"], "formats": ["svg"]})
    assert not r.is_error
    assert json.loads(r.content[0].text)["preview"] == "preview failed: Executable doesn't exist at /x/chrome"


def test_other_tools_return_tool_results(root):  # MCP-05..08 through the protocol
    s = srv.build(Tools(root))
    assert json.loads(call(s, "check", {"paths": ["decision.yaml"]}).content[0].text) == Tools(root).check(
        ["decision.yaml"])
    assert call(s, "layout", {"paths": ["quickstart.yaml"]}).content[0].text == Tools(root).layout_yaml(
        ["quickstart.yaml"])
    assert json.loads(call(s, "styles", {"paths": ["decision.yaml"]}).content[0].text) == Tools(root).styles(
        ["decision.yaml"])
    assert not call(s, "icons_search", {"query": "zzzz-no-such-icon"}).is_error


def test_errors_carry_the_cli_message_and_the_server_keeps_serving(root):  # MCP-10
    s = srv.build(Tools(root))

    async def go(c):
        bad = await c.call_tool("check", {"paths": []})
        outside = await c.call_tool("render", {"paths": ["../x.yaml"]})
        unknown = await c.call_tool("styles", {"paths": ["decision.yaml"], "select": "::"})
        good = await c.call_tool("check", {"paths": ["decision.yaml"]})
        return bad, outside, unknown, good

    bad, outside, unknown, good = run(s, go)
    assert bad.is_error and bad.content[0].text == "no diagrams found"
    assert outside.is_error and outside.content[0].text == "path outside root: ../x.yaml"
    assert unknown.is_error and unknown.content[0].text.startswith("invalid selector '::'")
    assert not good.is_error


def test_one_log_line_per_call_on_stderr(root, capfd):  # MCP-13
    s = srv.build(Tools(root))
    capfd.readouterr()

    async def go(c):
        await c.call_tool("check", {"paths": ["decision.yaml"]})
        await c.call_tool("check", {"paths": []})

    run(s, go)
    out, err = capfd.readouterr()
    lines = [ln for ln in err.splitlines() if ln.startswith("spinagram-mcp: ")]
    assert len(lines) == 2
    import re
    assert re.fullmatch(r"spinagram-mcp: check \d+ms ok", lines[0])
    assert re.fullmatch(r"spinagram-mcp: check \d+ms error", lines[1])
    assert out == ""


def test_renders_do_not_overlap(root, monkeypatch):  # MCP-14
    active, peak = [0], [0]
    guard = threading.Lock()

    def slow(self, paths, formats=None, only=None, out=None):
        with guard:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with guard:
            active[0] -= 1
        return {"written": []}

    monkeypatch.setattr(Tools, "render", slow)
    monkeypatch.setattr(srv, "png_previews", lambda scenes: [])
    s = srv.build(Tools(root))
    errors = []

    def worker():
        r = call(s, "render", {"paths": ["decision.yaml"]})
        errors.append(r.is_error)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [False] * 3 and peak[0] == 1


def test_skills_are_resources(root):  # MCP-15, MCP-16
    s = srv.build(Tools(root))
    listed = run(s, lambda c: c.list_resources()).resources
    want = skills.available()
    assert {str(r.uri): r.description for r in listed} == {f"spinagram://skills/{n}": sk.description
                                                         for n, sk in want.items()}
    got = run(s, lambda c: c.read_resource("spinagram://skills/spinagram")).contents[0]
    assert got.mime_type == "text/markdown"
    assert got.text == (want["spinagram"].path / "SKILL.md").read_text(encoding="utf-8")


# T16 (validation.md, iteration 2) --------------------------------------------------------------------
def test_styles_select_filters(root):  # MCP-07: `select` drops non-matching elements
    for name in ("styled.py", "brand.css"):
        shutil.copy(EXAMPLES / "styling" / name, root / name)
    s = srv.build(Tools(root))
    full = json.loads(call(s, "styles", {"paths": ["styled.py"]}).content[0].text)["elements"]
    edges = json.loads(call(s, "styles", {"paths": ["styled.py"], "select": "edge"}).content[0].text)["elements"]
    assert edges and len(edges) < len(full)
    assert {e["type"] for e in edges} == {"edge"}


def test_previews_follow_only(root, monkeypatch):  # MCP-03: previews of the rendered diagrams
    seen = []
    monkeypatch.setattr(srv, "png_previews", lambda scenes: seen.extend(sc.id for sc in scenes) or [])
    (root / "many.yaml").write_text("".join(f"- id: M{i}\n  title: Diagram {i}\n  nodes:\n    - {{id: a, title: A, "
                                            f"x: 100, y: 200}}\n" for i in range(3)), encoding="utf-8")
    r = call(srv.build(Tools(root)), "render", {"paths": ["many.yaml"], "only": ["M2"], "formats": ["svg"]})
    assert not r.is_error and seen == ["M2"]


def test_icons_search_pack_filter(root, tmp_path, monkeypatch):  # MCP-08: `pack` limits the packs searched
    from spinagram import icons

    monkeypatch.setenv("SPINAGRAM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    for pack in ("one", "two"):
        d = tmp_path / pack
        d.mkdir()
        (d / "dot.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        icons.register(pack, {"type": "dir", "path": str(d)})
        icons.fetch(icons.registry()[pack])
    s = srv.build(Tools(root))
    hits = lambda args: [c.text for c in call(s, "icons_search", args).content]  # noqa: E731  (one text per name)
    assert sorted(hits({"query": "dot"})) == ["one:dot", "two:dot"]
    assert hits({"query": "dot", "pack": ["two"]}) == ["two:dot"]


# T18 (validation.md, pass 4) -------------------------------------------------------------------------
def test_sibling_folder_sharing_the_root_prefix(tmp_path):  # MCP-09 (G1)
    root, sibling = tmp_path / "root", tmp_path / "root2"
    root.mkdir()
    sibling.mkdir()
    shutil.copy(EXAMPLES / "decision.yaml", sibling / "x.yaml")
    r = call(srv.build(Tools(root)), "check", {"paths": ["../root2/x.yaml"]})
    assert r.is_error and [c.text for c in r.content] == ["path outside root: ../root2/x.yaml"]


def test_error_result_has_one_text(root):  # MCP-10 (G9): exactly one text content
    r = call(srv.build(Tools(root)), "check", {"paths": []})
    assert r.is_error and len(r.content) == 1 and r.content[0].type == "text"


def test_codex_force_with_a_quoted_name(tmp_path):  # INST-08 (G5)
    import sys
    import tomllib

    from spinagram.mcp_server import install as ins

    kw = {"name": "my diagrams", "base": tmp_path, "home": tmp_path / "h"}
    path = ins.install("codex", command=[sys.executable, "-m", "spinagram", "mcp"], **kw)
    ins.install("codex", url="http://127.0.0.1:8766/mcp", force=True, **kw)
    assert tomllib.loads(path.read_text(encoding="utf-8"))["mcp_servers"] == {
        "my diagrams": {"url": "http://127.0.0.1:8766/mcp"}}


def test_icons_search_default_limit(root, tmp_path, monkeypatch):  # MCP-08 (G20): limit defaults to 40
    from spinagram import icons

    monkeypatch.setenv("SPINAGRAM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    d = tmp_path / "many"
    d.mkdir()
    for i in range(45):
        (d / f"dot-{i:02d}.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    icons.register("many", {"type": "dir", "path": str(d)})
    icons.fetch(icons.registry()["many"])
    assert len(Tools(root).icons_search("dot")) == 40
    r = call(srv.build(Tools(root)), "icons_search", {"query": "dot"})
    assert len(r.content) == 40
