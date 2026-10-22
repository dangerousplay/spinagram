"""The MCP tools as plain functions: the same results as the CLI, every path confined to a root folder."""
from __future__ import annotations

import json
from pathlib import Path

from .. import api, css, qa
from ..theme import Theme
from ..yaml_io import load


class Tools:
    """Tool calls over the specs under ``root``; ``theme``, ``layout`` and ``formats`` are the server defaults."""

    def __init__(self, root: str | Path | None = None, theme: str | None = None, layout: str | None = None,
                 formats: list[str] | None = None):
        self.root = Path(root or Path.cwd()).resolve()
        # the server's own theme is resolved now, against its cwd, and may live outside the root
        self.theme = str(Path(theme).resolve()) if theme and Path(theme).exists() else theme
        self.layout, self.formats = layout, formats or ["svg", "png"]

    def path(self, p: str) -> Path:
        """``p`` resolved under the root (symlinks followed); ValueError when it leaves the root."""
        q = (self.root / p).resolve()
        if not q.is_relative_to(self.root):
            raise ValueError(f"path outside root: {p}")
        return q

    def _theme(self, theme: str | None) -> Theme:
        """A call's theme (a folder under the root, or a built-in name), else the server's."""
        if not theme:
            return Theme.load(self.theme)
        return Theme.load(self.path(theme) if (self.root / theme).exists() else theme)

    def diagrams(self, paths: list[str], only: list[str] | None = None):
        files = [self.path(p) for p in paths]
        diagrams = [d for f in files for d in load(str(f))]
        if only:
            diagrams = [d for d in diagrams if d.id in set(only)]
        if not diagrams:
            raise ValueError("no diagrams found")
        return diagrams

    def render(self, paths: list[str], formats: list[str] | None = None, only: list[str] | None = None,
               out: str | None = None, theme: str | None = None, layout: str | None = None) -> dict:
        diagrams = self.diagrams(paths, only)
        dest = self.path(out or "out")
        written = api.render(diagrams, dest, theme=self._theme(theme), formats=formats or self.formats, gallery=True,
                             layout=layout or self.layout)
        return {"written": [Path(p).resolve().relative_to(self.root).as_posix() for p in written]}

    def scenes(self, paths: list[str], only: list[str] | None = None, theme: str | None = None,
               layout: str | None = None):
        return api.scenes(self.diagrams(paths, only), self._theme(theme), layout or self.layout)

    def check(self, paths: list[str], only: list[str] | None = None, theme: str | None = None,
              layout: str | None = None) -> dict:
        scs = self.scenes(paths, only, theme, layout)
        return {"diagrams": len(scs), "issues": [str(i) for sc in scs for i in qa.check(sc)]}

    def layout_yaml(self, paths: list[str], only: list[str] | None = None, theme: str | None = None,
                    layout: str | None = None) -> str:
        import yaml

        from ..autolayout import apply_layout
        from ..yaml_io import dump

        th = self._theme(theme)
        docs = [dump(apply_layout(d, th, layout or self.layout)) for d in self.diagrams(paths, only)]
        return yaml.safe_dump(docs if len(docs) > 1 else docs[0], sort_keys=False, allow_unicode=True, width=120)

    def styles(self, paths: list[str], only: list[str] | None = None, select: str | None = None,
               theme: str | None = None) -> dict | list:
        th = self._theme(theme)
        reports = []
        ds = self.diagrams(paths, only)
        for d, sc in zip(ds, api.scenes(ds, th, self.layout)):
            r = css.inspect(d, th)
            if select:
                keys = css.select(d, select)
                r["elements"] = [e for e in r["elements"] if e["key"] in keys]
            r["issues"] = [i.to_dict() for i in qa.check(sc)]  # as ``check --json``
            reports.append(r)
        return json.loads(json.dumps(reports if len(reports) > 1 else reports[0], ensure_ascii=False))

    def icons_search(self, query: str, pack: list[str] | None = None, limit: int = 40) -> list[str]:
        from .. import icons

        packs = icons.registry()
        hits = icons.search(query, [packs[n] for n in (pack or packs) if n in packs])
        return [f"{p}:{name}" for p, name, _ in hits[:limit]]
