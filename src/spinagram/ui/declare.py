"""Where an element of the styles report is declared: a text search of its spec file (first matching line).

Specs do not keep source positions, so this looks for what authors write: ``id: users`` or the title in YAML,
``id="users"`` or the quoted title in Python, ``a -> b`` or ``from:``/``to:`` for YAML edges and the quoted
label for Python edges.
"""
from __future__ import annotations

import re


def _quoted(v: str | None) -> str | None:
    return rf"""(["']){re.escape(v)}\1""" if v else None


def _yaml(key: str, v: str | None) -> str | None:
    return rf"""(?:^|[\s{{,]){key}:\s*(["']?){re.escape(v)}\1\s*(?:[,}}#]|$)""" if v else None


def _patterns(py: bool, element: dict) -> list[str | None]:
    typ, eid, attrs = element["type"], element.get("id"), element.get("attrs") or {}
    label = attrs.get("label")
    if typ == "edge":
        if py:
            return [_quoted(label)]
        a, b = (re.escape(attrs.get(k) or "") for k in ("from", "to"))
        if not a or not b:
            return []
        port = r"(?:\.[\w-]+)?"
        return [rf"(?<![\w.-]){a}{port}\s*->\s*{b}{port}(?![\w-])",
                rf"(?=.*{_yaml('from', attrs['from'])})(?=.*{_yaml('to', attrs['to'])})"]
    if typ == "diagram":
        if py:
            return [rf"\bDiagram\(\s*{_quoted(eid)}" if eid else None]
        return [_yaml("id", eid)]
    if py:
        return [rf"\bid\s*=\s*{_quoted(eid)}" if eid else None, _quoted(label)]
    return [_yaml("id", eid), _yaml("(?:title|label)", label)]


def locate(text: str, suffix: str, element: dict) -> int | None:
    """The 1-based line of ``text`` declaring ``element`` (a ``css.inspect`` element), or None.

    ``suffix`` is the spec file's suffix: ``.py`` searches Python, anything else YAML."""
    lines = text.splitlines()
    for pat in _patterns(suffix == ".py", element):
        if pat is None:
            continue
        rx = re.compile(pat)
        for i, line in enumerate(lines, 1):
            if rx.search(line):
                return i
    return None
