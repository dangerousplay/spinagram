"""Write spinagram's MCP server entry into a coding agent's config file (project or user scope).

Each agent keeps MCP servers in its own file and shape (``AGENTS``); entries for other servers and every
other key are kept. JSON files are rewritten with the same values; Codex's TOML keeps its text outside our
table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .. import __version__

# agent: (file in the project, file under the home folder)
AGENTS: dict[str, tuple[str, str]] = {
    "claude": (".mcp.json", ".claude.json"),
    "codex": (".codex/config.toml", ".codex/config.toml"),
    "copilot": (".vscode/mcp.json", ".copilot/mcp-config.json"),  # VS Code project file, Copilot CLI user file
    "cursor": (".cursor/mcp.json", ".cursor/mcp.json"),
    "gemini": (".gemini/settings.json", ".gemini/settings.json"),
    "opencode": ("opencode.json", ".config/opencode/opencode.json"),
}


def launch(args: list[str], uvx: bool = False) -> list[str]:
    """The command an agent runs to start the server: this Python, or ``uvx`` pinned to this version."""
    if uvx:
        return ["uvx", "--from", f"spinagram[mcp]=={__version__}", "spinagram", "mcp", *args]
    return [sys.executable, "-m", "spinagram", "mcp", *args]


def server_args(theme: str | None = None, root: str | None = None, formats: str | None = None,
                layout: str | None = None) -> list[str]:
    """``spinagram mcp`` flags for the entry; ``root`` becomes absolute."""
    out = ["-t", theme] if theme else []
    if root:
        out += ["--root", str(Path(root).resolve())]
    if formats:
        out += ["--formats", formats]
    if layout:
        out += ["--layout", layout]
    return out


def config_path(agent: str, user: bool = False, base: Path | None = None, home: Path | None = None) -> Path:
    if agent not in AGENTS:
        raise ValueError(f"unknown agent {agent!r}; known: {', '.join(AGENTS)}")
    project, home_file = AGENTS[agent]
    return (home or Path.home()) / home_file if user else (base or Path.cwd()) / project


def _key(agent: str, user: bool) -> str:
    return {"opencode": "mcp", "copilot": "mcpServers" if user else "servers"}.get(agent, "mcpServers")


def entry(agent: str, user: bool, command: list[str] | None = None, url: str | None = None) -> dict:
    """The server entry in ``agent``'s shape: stdio ``command``, or the HTTP ``url`` of a running server."""
    cli = agent == "copilot" and user  # Copilot CLI
    if url:
        e = {"claude": {"type": "http", "url": url}, "gemini": {"httpUrl": url},
             "opencode": {"type": "remote", "url": url, "enabled": True},
             "copilot": {"type": "http", "url": url}}.get(agent, {"url": url})
    elif agent == "opencode":
        e = {"type": "local", "command": command, "enabled": True}
    else:
        kind = {"claude": "stdio", "copilot": "local" if cli else "stdio"}.get(agent)
        e = ({"type": kind} if kind else {}) | {"command": command[0], "args": command[1:]}
    return e | ({"tools": ["*"]} if cli else {})


def install(agent: str, *, command: list[str] | None = None, url: str | None = None, user: bool = False,
            name: str = "spinagram", force: bool = False, base: Path | None = None, home: Path | None = None) -> Path:
    """Add the entry to ``agent``'s config; FileExistsError when ``name`` is there (unless ``force``),
    ValueError when the file does not parse. Returns the file written."""
    path = config_path(agent, user, base, home)
    new = entry(agent, user, command, url)
    text = path.read_text(encoding="utf-8") if path.exists() else None
    try:
        data = json.loads(text) if text is not None else {}
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
    except ValueError as exc:
        raise ValueError(f"cannot parse {path}: {exc}") from None
    servers = data.setdefault(_key(agent, user), {})
    if name in servers and not force:
        raise FileExistsError(f"already installed: {name} in {path} (use --force to replace)")
    servers[name] = new
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
