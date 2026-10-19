"""Agent MCP config writers (spec: .specs/features/mcp-server/spec.md, INST-01..09, AGENT table)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from spinagram import __version__
from spinagram.mcp_server import install as ins

CMD = [sys.executable, "-m", "spinagram", "mcp"]
# agent: (project file, user file, key) from the spec's AGENT table
FILES = {
    "claude": (".mcp.json", ".claude.json", "mcpServers"),
    "cursor": (".cursor/mcp.json", ".cursor/mcp.json", "mcpServers"),
    "gemini": (".gemini/settings.json", ".gemini/settings.json", "mcpServers"),
    "copilot": (".vscode/mcp.json", ".copilot/mcp-config.json", None),
    "opencode": ("opencode.json", ".config/opencode/opencode.json", "mcp"),
}
STDIO = {
    "claude": {"type": "stdio", "command": CMD[0], "args": CMD[1:]},
    "cursor": {"command": CMD[0], "args": CMD[1:]},
    "gemini": {"command": CMD[0], "args": CMD[1:]},
    "opencode": {"type": "local", "command": CMD, "enabled": True},
}
URL = "http://127.0.0.1:8766/mcp"
HTTP = {
    "claude": {"type": "http", "url": URL},
    "cursor": {"url": URL},
    "gemini": {"httpUrl": URL},
    "opencode": {"type": "remote", "url": URL, "enabled": True},
}


@pytest.fixture
def dirs(tmp_path):
    base, home = tmp_path / "proj", tmp_path / "home"
    base.mkdir()
    home.mkdir()
    return base, home


def read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_launch_command():  # INST-05
    assert ins.launch([]) == CMD
    assert ins.launch(["--root", "/x"]) == CMD + ["--root", "/x"]
    assert ins.launch(["-t", "t"], uvx=True) == ["uvx", "--from", f"spinagram[mcp]=={__version__}", "spinagram", "mcp",
                                                  "-t", "t"]


def test_server_args(tmp_path, monkeypatch):  # INST-04: flags after `mcp`, root absolute
    monkeypatch.chdir(tmp_path)
    (tmp_path / "specs").mkdir()
    assert ins.server_args(theme="brand", root="specs", formats="svg,excalidraw", layout="dot") == [
        "-t", "brand", "--root", str((tmp_path / "specs").resolve()), "--formats", "svg,excalidraw", "--layout", "dot"]
    assert ins.server_args() == []


@pytest.mark.parametrize("agent", list(STDIO))
@pytest.mark.parametrize("user", [False, True])
def test_stdio_entry_per_agent_and_scope(agent, user, dirs):  # INST-01, INST-02, AGENT table
    base, home = dirs
    path = ins.install(agent, command=CMD, user=user, base=base, home=home)
    proj, usr, key = FILES[agent]
    assert path == (home / usr if user else base / proj)
    assert read(path) == {key: {"spinagram": STDIO[agent]}}


@pytest.mark.parametrize("user", [False, True])
def test_copilot_vscode_and_cli(user, dirs):  # AGENT table: VS Code project file, Copilot CLI user file
    base, home = dirs
    path = ins.install("copilot", command=CMD, user=user, base=base, home=home)
    if user:
        assert path == home / ".copilot/mcp-config.json"
        assert read(path) == {"mcpServers": {"spinagram": {"type": "local", "command": CMD[0], "args": CMD[1:],
                                                           "tools": ["*"]}}}
    else:
        assert path == base / ".vscode/mcp.json"
        assert read(path) == {"servers": {"spinagram": {"type": "stdio", "command": CMD[0], "args": CMD[1:]}}}


@pytest.mark.parametrize("agent", list(HTTP))
def test_http_entry_per_agent(agent, dirs):  # INST-06
    base, home = dirs
    path = ins.install(agent, url=URL, base=base, home=home)
    assert read(path)[FILES[agent][2]]["spinagram"] == HTTP[agent]


@pytest.mark.parametrize("user", [False, True])
def test_copilot_http(user, dirs):  # INST-06 (copilot)
    base, home = dirs
    got = read(ins.install("copilot", url=URL, user=user, base=base, home=home))
    want = {"type": "http", "url": URL} | ({"tools": ["*"]} if user else {})
    assert got["mcpServers" if user else "servers"]["spinagram"] == want


def test_name_and_other_servers_survive(dirs):  # INST-07, --name
    base, home = dirs
    cfg = home / ".claude.json"
    other = {"numStartups": 42, "projects": {"/x": {"mcpServers": {"p": {"command": "p"}}}},
             "mcpServers": {"github": {"type": "http", "url": "https://example.test/mcp"}}}
    cfg.write_text(json.dumps(other), encoding="utf-8")
    ins.install("claude", command=CMD, user=True, name="diagrams", base=base, home=home)
    got = read(cfg)
    assert got["mcpServers"].pop("diagrams") == STDIO["claude"]
    assert got == other


def test_duplicate_is_refused_unchanged(dirs):  # INST-08
    base, home = dirs
    path = ins.install("cursor", command=CMD, base=base, home=home)
    before = path.read_bytes()
    with pytest.raises(FileExistsError) as exc:
        ins.install("cursor", url=URL, base=base, home=home)
    assert str(exc.value) == f"already installed: spinagram in {path} (use --force to replace)"
    assert path.read_bytes() == before


def test_force_replaces_only_the_entry(dirs):  # INST-08 (--force)
    base, home = dirs
    path = base / ".mcp.json"
    path.write_text(json.dumps({"mcpServers": {"spinagram": {"command": "old"}, "keep": {"command": "k"}},
                                "extra": [1, 2]}), encoding="utf-8")
    ins.install("claude", url=URL, force=True, base=base, home=home)
    assert read(path) == {"mcpServers": {"spinagram": HTTP["claude"], "keep": {"command": "k"}}, "extra": [1, 2]}


@pytest.mark.parametrize("text", ["{not json", "// comment\n{}", "[]"])
def test_unparseable_file_is_left_alone(text, dirs):  # INST-09
    base, home = dirs
    path = base / "opencode.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=rf"^cannot parse {path}: "):
        ins.install("opencode", command=CMD, base=base, home=home)
    assert path.read_text(encoding="utf-8") == text


def test_unknown_agent(dirs):  # INST-10 (function level)
    base, home = dirs
    with pytest.raises(ValueError, match=r"^unknown agent 'vim'; known: claude, codex, copilot, cursor, gemini, "
                                         r"opencode$"):
        ins.install("vim", command=CMD, base=base, home=home)


# T6: Codex TOML --------------------------------------------------------------------------------------
import tomllib  # noqa: E402

CODEX_OTHER = """\
# my settings
model = "o4"

[mcp_servers.github]
url = "https://example.test/mcp"

[profiles.fast]
model = "mini"   # keep this comment
"""


@pytest.mark.parametrize("user", [False, True])
def test_codex_new_file(user, dirs):  # INST-01, INST-02 (codex)
    base, home = dirs
    path = ins.install("codex", command=CMD, user=user, base=base, home=home)
    assert path == (home if user else base) / ".codex/config.toml"
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {
        "mcp_servers": {"spinagram": {"command": CMD[0], "args": CMD[1:]}}}


def test_codex_keeps_other_text(dirs):  # INST-07: same text outside the server's table
    base, home = dirs
    path = base / ".codex/config.toml"
    path.parent.mkdir()
    path.write_text(CODEX_OTHER, encoding="utf-8")
    ins.install("codex", command=CMD, base=base, home=home)
    text = path.read_text(encoding="utf-8")
    assert text.startswith(CODEX_OTHER)
    data = tomllib.loads(text)
    assert data["mcp_servers"]["spinagram"] == {"command": CMD[0], "args": CMD[1:]}
    assert data["mcp_servers"]["github"] == {"url": "https://example.test/mcp"}
    assert data["profiles"] == {"fast": {"model": "mini"}}


def test_codex_url_and_quoted_values(dirs):  # INST-06 (codex: url), values escaped as TOML strings
    base, home = dirs
    path = ins.install("codex", url='http://h/"mcp"\\x', name="my diagrams", base=base, home=home)
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"mcp_servers": {"my diagrams": {"url": 'http://h/"mcp"\\x'}}}


def test_codex_duplicate_and_force(dirs):  # INST-08 (codex)
    base, home = dirs
    path = base / ".codex/config.toml"
    path.parent.mkdir()
    path.write_text(CODEX_OTHER + '\n[mcp_servers.spinagram]\ncommand = "old"\n\n[mcp_servers.spinagram.env]\nA = "1"\n'
                    '\n[tail]\nx = 1\n', encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(FileExistsError, match=r"^already installed: spinagram in "):
        ins.install("codex", url=URL, base=base, home=home)
    assert path.read_bytes() == before
    ins.install("codex", url=URL, force=True, base=base, home=home)
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data["mcp_servers"]["spinagram"] == {"url": URL}                 # old table and its env subtable gone
    assert data["tail"] == {"x": 1} and data["mcp_servers"]["github"]
    assert text.startswith(CODEX_OTHER) and text.endswith("[tail]\nx = 1\n")


def test_codex_invalid_toml_left_alone(dirs):  # INST-09 (codex)
    base, home = dirs
    path = base / ".codex/config.toml"
    path.parent.mkdir()
    path.write_text("[broken\n", encoding="utf-8")
    with pytest.raises(ValueError, match=rf"^cannot parse {path}: "):
        ins.install("codex", command=CMD, base=base, home=home)
    assert path.read_text(encoding="utf-8") == "[broken\n"


# T11 (validation.md, iteration 1) --------------------------------------------------------------------
def test_json_text_is_indented_two(dirs):  # edge case: rewritten with indent 2
    base, home = dirs
    path = ins.install("cursor", url=URL, base=base, home=home)
    assert path.read_text(encoding="utf-8") == ('{\n  "mcpServers": {\n    "spinagram": {\n      "url": "' + URL +
                                                '"\n    }\n  }\n}\n')


def test_codex_force_keeps_the_comment_above_the_next_table(dirs):  # INST-07
    base, home = dirs
    path = base / ".codex/config.toml"
    path.parent.mkdir()
    path.write_text('[mcp_servers.spinagram]\ncommand = "old"\n\n# profiles below\n[profiles.fast]\nmodel = "m"\n',
                    encoding="utf-8")
    ins.install("codex", url=URL, force=True, base=base, home=home)
    assert path.read_text(encoding="utf-8") == (f'[mcp_servers.spinagram]\nurl = "{URL}"\n\n# profiles below\n'
                                                '[profiles.fast]\nmodel = "m"\n')
