"""The MCP binding: spinagram's tools and skills on an ``MCPServer`` (official SDK v2)."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from functools import wraps
from pathlib import Path

from mcp.server.mcpserver import Image, MCPServer
from mcp.types import CallToolResult, TextContent

from .. import __version__, skills
from .tools import Tools

MAX_PREVIEWS = 4
INSTRUCTIONS = ("spinagram renders diagrams-as-code specs (YAML or Python) to SVG, PNG, PowerPoint, Figma and "
                "Excalidraw. Read the resource spinagram://skills/spinagram before writing a spec. Paths are "
                "relative to the server's root folder.")


def png_previews(scenes) -> list[bytes]:
    """PNG bytes at 1x of each scene; ImportError without the png extra."""
    import playwright  # noqa: F401  (the png extra)

    from ..backends.png import PngBackend

    with tempfile.TemporaryDirectory() as tmp:
        return [p.read_bytes() for p in PngBackend(scale=1).render(scenes, Path(tmp))]


def _logged(fn):
    """Log ``spinagram-mcp: <tool> <ms>ms ok|error`` on stderr; a failure is an error result with the CLI message
    (the SDK's own ToolError would prefix it with "Error executing tool …")."""
    @wraps(fn)
    def run(*args, **kwargs):
        t0, state = time.perf_counter(), "error"
        try:
            out = fn(*args, **kwargs)
            state = "ok"
            return out
        except Exception as exc:  # the CLI prints these after "spinagram: error: "
            return CallToolResult(content=[TextContent(type="text", text=str(exc))], is_error=True)
        finally:
            print(f"spinagram-mcp: {fn.__name__} {round((time.perf_counter() - t0) * 1000)}ms {state}", file=sys.stderr)
    return run


def build(tools: Tools) -> MCPServer:
    server = MCPServer("spinagram", version=__version__, instructions=INSTRUCTIONS)
    writing = threading.Lock()

    @server.tool(description="Render spec files or folders (paths under the root) to files in `out` (default "
                             "out/); returns the written paths and PNG previews of the first diagrams.")
    @_logged
    def render(paths: list[str], formats: list[str] | None = None, only: list[str] | None = None,
               out: str | None = None) -> list:
        with writing:
            result = tools.render(paths, formats, only, out)
        images = []
        try:
            images = [Image(data=b, format="png") for b in png_previews(tools.scenes(paths, only)[:MAX_PREVIEWS])]
        except ImportError:
            result["preview"] = "preview needs spinagram[png]"
        except Exception as exc:
            result["preview"] = "preview failed: " + (str(exc).strip().splitlines() or [type(exc).__name__])[0]
        return [json.dumps(result, ensure_ascii=False), *images]

    @server.tool(description="QA check: text overflow, labels hiding arrowheads or covering boxes, edges through "
                             "boxes. Returns the diagram count and one string per issue.")
    @_logged
    def check(paths: list[str], only: list[str] | None = None) -> dict:
        return tools.check(paths, only)

    @server.tool(description="Freeze automatic positions: the explicit YAML spec, as `spinagram layout` prints it.")
    @_logged
    def layout(paths: list[str], only: list[str] | None = None) -> str:
        return tools.layout_yaml(paths, only)

    @server.tool(description="CSS style report (`spinagram check --json`): each element's computed style, matching "
                             "rules and overrides; `select` keeps elements matching a CSS selector.")
    @_logged
    def styles(paths: list[str], only: list[str] | None = None, select: str | None = None) -> dict | list:
        return tools.styles(paths, only, select)

    @server.tool(description="Find icon names (pack:name) in the downloaded icon packs.")
    @_logged
    def icons_search(query: str, pack: list[str] | None = None, limit: int = 40) -> list[str]:
        return tools.icons_search(query, pack, limit)

    for skill in skills.available().values():
        server.resource(f"spinagram://skills/{skill.name}", name=skill.name, description=skill.description,
                        mime_type="text/markdown")(_reader(skill.path / "SKILL.md"))
    return server


def _reader(path: Path):
    def read() -> str:
        return path.read_text(encoding="utf-8")
    return read
