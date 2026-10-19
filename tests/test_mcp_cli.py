"""spinagram mcp and spinagram mcp install on the command line (spec: .specs/features/mcp-server/spec.md)."""
from __future__ import annotations

import subprocess
import sys

from spinagram import __version__


def test_python_m_spinagram_runs_the_cli():  # INST-05: the launch command agent configs use
    out = subprocess.run([sys.executable, "-m", "spinagram", "-V"], capture_output=True, text=True)
    assert out.returncode == 0
    assert out.stdout.strip() == f"spinagram {__version__}"


# T4: spinagram mcp ----------------------------------------------------------------------------------
import json  # noqa: E402
import os  # noqa: E402
import socket  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import anyio  # noqa: E402
import pytest  # noqa: E402

from spinagram.cli import main  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_missing_extra_message(monkeypatch, capsys):  # MCP-12
    import spinagram.mcp_server as pkg

    monkeypatch.setitem(sys.modules, "spinagram.mcp_server.server", None)   # import fails like a missing extra
    monkeypatch.delattr(pkg, "server", raising=False)                       # even after an earlier test imported it
    assert main(["mcp"]) == 2
    assert capsys.readouterr().err.strip() == "spinagram: mcp needs the mcp extra: pip install 'spinagram[mcp]'"


def test_stdio_server_answers(tmp_path):  # MCP-01 over a real stdio pipe
    pytest.importorskip("mcp")
    from mcp import Client, StdioServerParameters

    params = StdioServerParameters(command=sys.executable,
                                   args=["-m", "spinagram", "mcp", "--root", str(EXAMPLES)])

    async def go():
        async with Client(params) as c:
            return await c.call_tool("check", {"paths": ["decision.yaml"]})

    r = anyio.run(go)
    assert not r.is_error and json.loads(r.content[0].text)["diagrams"] == 1


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_http_server_answers():  # HTTP-01
    pytest.importorskip("mcp")
    from mcp import Client

    port = _free_port()
    proc = subprocess.Popen([sys.executable, "-m", "spinagram", "mcp", "--root", str(EXAMPLES), "--http", str(port)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ})
    try:
        for _ in range(100):
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)

        async def go():
            async with Client(f"http://127.0.0.1:{port}/mcp") as c:
                return await c.call_tool("check", {"paths": ["decision.yaml"]})

        r = anyio.run(go)
        assert not r.is_error and json.loads(r.content[0].text) == {"diagrams": 1, "issues": []}
    finally:
        proc.terminate()
        proc.wait(10)


def test_flags_reach_the_server(monkeypatch, tmp_path):  # MCP-11 (server defaults), HTTP-01 (default host)
    pytest.importorskip("mcp")
    from mcp.server.mcpserver import MCPServer

    from spinagram.mcp_server import server as srv

    seen = {}
    real_build = srv.build

    def build(tools):
        seen["tools"] = tools
        return real_build(tools)

    monkeypatch.setattr(srv, "build", build)
    monkeypatch.setattr(MCPServer, "run", lambda self, transport="stdio", **kw: seen.update(transport=transport, **kw))
    assert main(["mcp", "-t", "default", "--layout", "flex", "--formats", "svg,excalidraw", "--root", str(tmp_path),
                 "--http", "8899"]) == 0
    t = seen["tools"]
    assert (t.root, t.theme, t.layout, t.formats) == (tmp_path.resolve(), "default", "flex", ["svg", "excalidraw"])
    assert (seen["transport"], seen["host"], seen["port"]) == ("streamable-http", "127.0.0.1", 8899)
    seen.clear()
    assert main(["mcp", "--root", str(tmp_path)]) == 0
    assert seen == {"tools": seen["tools"], "transport": "stdio"}


def test_non_loopback_host_warns(monkeypatch, capsys):  # HTTP-02
    pytest.importorskip("mcp")
    from mcp.server.mcpserver import MCPServer

    monkeypatch.setattr(MCPServer, "run", lambda self, transport="stdio", **kw: None)
    assert main(["mcp", "--http", "8900", "--host", "0.0.0.0"]) == 0
    assert capsys.readouterr().err.strip() == "warning: no authentication on 0.0.0.0:8900"
    for host in ("127.0.0.1", "localhost", "::1"):
        assert main(["mcp", "--http", "8900", "--host", host]) == 0
        assert "warning" not in capsys.readouterr().err


# T7: spinagram mcp install ---------------------------------------------------------------------------
KNOWN = "claude, codex, copilot, cursor, gemini, opencode"


@pytest.fixture
def proj(tmp_path, monkeypatch):
    base, home = tmp_path / "proj", tmp_path / "home"
    base.mkdir()
    home.mkdir()
    monkeypatch.chdir(base)
    monkeypatch.setenv("HOME", str(home))
    return base, home


def test_install_prints_the_file(proj, capsys):  # INST-01
    base, _ = proj
    assert main(["mcp", "install", "-a", "cursor"]) == 0
    path = base / ".cursor/mcp.json"
    assert capsys.readouterr().out.strip() == f"installed spinagram in {path}"
    assert json.loads(path.read_text())["mcpServers"]["spinagram"] == {"command": sys.executable,
                                                                       "args": ["-m", "spinagram", "mcp"]}


def test_install_user_scope(proj, capsys):  # INST-02 through the CLI
    _, home = proj
    assert main(["mcp", "install", "-a", "claude", "--user"]) == 0
    assert "spinagram" in json.loads((home / ".claude.json").read_text())["mcpServers"]


def test_install_several_agents(proj, capsys):  # INST-03
    base, _ = proj
    assert main(["mcp", "install", "-a", "claude", "-a", "codex", "--name", "diagrams"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [f"installed diagrams in {base / '.mcp.json'}", f"installed diagrams in {base / '.codex/config.toml'}"]


def test_install_flags_become_args(proj, capsys):  # INST-04, INST-05 (--uvx), INST-06 (--url)
    base, _ = proj
    (base / "specs").mkdir()
    assert main(["mcp", "install", "-a", "gemini", "-t", "brand", "--root", "specs", "--formats", "svg",
                 "--layout", "elk"]) == 0
    e = json.loads((base / ".gemini/settings.json").read_text())["mcpServers"]["spinagram"]
    assert e["args"] == ["-m", "spinagram", "mcp", "-t", "brand", "--root", str((base / "specs").resolve()),
                         "--formats", "svg", "--layout", "elk"]
    assert main(["mcp", "install", "-a", "opencode", "--uvx"]) == 0
    e = json.loads((base / "opencode.json").read_text())["mcp"]["spinagram"]
    assert e["command"] == ["uvx", "--from", f"spinagram[mcp]=={__version__}", "spinagram", "mcp"]
    assert main(["mcp", "install", "-a", "claude", "--url", "http://127.0.0.1:8766/mcp"]) == 0
    assert json.loads((base / ".mcp.json").read_text())["mcpServers"]["spinagram"] == {
        "type": "http", "url": "http://127.0.0.1:8766/mcp"}


def test_install_duplicate_exit_1(proj, capsys):  # INST-08
    base, _ = proj
    assert main(["mcp", "install", "-a", "cursor"]) == 0
    before = (base / ".cursor/mcp.json").read_bytes()
    capsys.readouterr()
    assert main(["mcp", "install", "-a", "cursor", "--url", "http://x/mcp"]) == 1
    assert capsys.readouterr().err.strip() == (f"spinagram: already installed: spinagram in {base / '.cursor/mcp.json'} "
                                               "(use --force to replace)")
    assert (base / ".cursor/mcp.json").read_bytes() == before
    assert main(["mcp", "install", "-a", "cursor", "--url", "http://x/mcp", "--force"]) == 0
    assert json.loads((base / ".cursor/mcp.json").read_text())["mcpServers"]["spinagram"] == {"url": "http://x/mcp"}


def test_install_unparseable_exit_2(proj, capsys):  # INST-09
    base, _ = proj
    (base / ".mcp.json").write_text("{oops", encoding="utf-8")
    assert main(["mcp", "install", "-a", "claude"]) == 2
    assert capsys.readouterr().err.startswith(f"spinagram: error: cannot parse {base / '.mcp.json'}: ")
    assert (base / ".mcp.json").read_text() == "{oops"


def test_install_unknown_or_missing_agent_exit_2(proj, capsys):  # INST-10
    base, _ = proj
    assert main(["mcp", "install", "-a", "claude", "-a", "vim"]) == 2
    assert capsys.readouterr().err.strip() == f"spinagram: error: unknown agent 'vim'; known: {KNOWN}"
    assert not (base / ".mcp.json").exists()                                 # nothing written when one agent is wrong
    assert main(["mcp", "install"]) == 2
    assert capsys.readouterr().err.strip() == f"spinagram: error: pass -a AGENT (known: {KNOWN})"


def test_install_server_key_not_an_object_exit_2(proj, capsys):  # INST-09 through the CLI
    base, _ = proj
    (base / ".mcp.json").write_text('{"mcpServers": []}', encoding="utf-8")
    assert main(["mcp", "install", "-a", "claude"]) == 2
    assert capsys.readouterr().err.strip() == (f"spinagram: error: cannot parse {base / '.mcp.json'}: "
                                               "mcpServers is not an object")
