"""Terminal rendering of :func:`spinagram.css.inspect` reports (``spinagram check --styles``).

Laid out like a browser's styles panel: per element the computed values, then the matching rules from the
winning one down, overridden declarations struck through, then inherited values and pseudo-elements.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")


def use_color(mode: str, stream) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return bool(getattr(stream, "isatty", lambda: False)()) and "NO_COLOR" not in os.environ


class _Pen:
    def __init__(self, color: bool):
        self.color = color

    def _sgr(self, code: str, s: str) -> str:
        return f"\x1b[{code}m{s}\x1b[0m" if self.color and s else s

    def bold(self, s: str) -> str:
        return self._sgr("1", s)

    def dim(self, s: str) -> str:
        return self._sgr("2", s)

    def strike(self, s: str) -> str:
        return self._sgr("9;2", s) if self.color else f"{s}  (overridden)"

    def sel(self, s: str) -> str:
        return self._sgr("36", s)          # cyan: selectors

    def prop(self, s: str) -> str:
        return self._sgr("35", s)          # magenta: property names

    def warn(self, s: str) -> str:
        return self._sgr("33", s)

    def err(self, s: str) -> str:
        return self._sgr("31", s)

    def swatches(self, value: str) -> str:
        """``value`` with a truecolor block before every #RRGGBB in it (colour mode only)."""
        if not self.color:
            return value

        def block(m: re.Match) -> str:
            h = m.group()[1:]
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
            return f"\x1b[48;2;{r};{g};{b}m  \x1b[0m {m.group()}"

        return _HEX.sub(block, value)


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, list):
        if len(v) == 5 and isinstance(v[3], str):  # box-shadow (dx, dy, blur, colour, alpha)
            return f"{v[0]:g} {v[1]:g} {v[2]:g} {v[3]} / {v[4]:g}"
        return " ".join(_fmt(x) for x in v) or "none"
    return str(v)


def _origin(origin: str, line: int | None, base: Path | None) -> str:
    if origin == "inline":
        return "inline"
    p = Path(origin)
    if base is not None and p.is_absolute():
        try:
            origin = p.relative_to(base).as_posix()
        except ValueError:
            pass
    return f"{origin}:{line}" if line else origin


def element_label(e: dict) -> str:
    """``node#api.critical`` / ``edge api → db`` — how the element reads in a selector."""
    if e["type"] == "edge":
        a = e["attrs"]
        cls = "".join(f".{c}" for c in e["classes"])
        return f"edge{cls} {a.get('from')} → {a.get('to')}"
    return e["type"] + (f"#{e['id']}" if e["id"] else "") + "".join(f".{c}" for c in e["classes"])


def _rules(decls: list[dict]) -> list[tuple[dict, list[dict]]]:
    """Declarations grouped by rule, winning rule first; inside a rule in source order."""
    groups: dict[tuple, list[dict]] = {}
    for d in reversed(decls):
        groups.setdefault((d["origin"], d["rule_line"], d["selector"], d["important"]), []).append(d)
    return [(ds[0], ds[::-1]) for ds in groups.values()]


def _section(out: list[str], pen: _Pen, t: dict, base: Path | None, labels: dict[str, str], indent: str) -> None:
    for head, decls in _rules(t["decls"]):
        sel = head["selector"] or "inline css"
        where = _origin(head["origin"], head["rule_line"], base)
        spec = "" if head["specificity"] is None else " (" + ",".join(map(str, head["specificity"])) + ")"
        out.append(f"{indent}{pen.sel(sel)}  {pen.dim(where + spec)}")
        for d in decls:
            val = d["value"] + ("" if d["resolved"] == d["value"] else f" → {d['resolved']}")
            imp = " !important" if d["important"] else ""
            text = f"{d['property']}: {val}{imp}"
            if d["status"] == "overridden":
                out.append(f"{indent}    {pen.strike(text)}")
            elif d["status"] in ("invalid", "unknown"):
                out.append(f"{indent}    {pen.err(text)}  {pen.warn('⚠ ' + d.get('message', d['status']))}")
            else:
                out.append(f"{indent}    {pen.prop(d['property'])}: {pen.swatches(val)}{imp}")
    by_src: dict[str | None, list[dict]] = {}
    for i in t["inherited"]:
        by_src.setdefault(i["from"], []).append(i)
    for src, items in by_src.items():
        out.append(f"{indent}{pen.dim('inherited from')} {pen.sel(labels.get(src, src or '?'))}")
        for i in items:
            out.append(f"{indent}    {pen.prop(i['property'])}: {pen.swatches(_fmt(i['value']))}")


def render(report: dict, *, color: bool = False, keys: list[str] | None = None, base: Path | None = None,
           unused_selectors: bool = True) -> str:
    """One diagram's report as text. ``keys`` limits the elements shown (``--select``). With several
    diagrams, pass ``unused_selectors=False`` and print :func:`unused` once (a selector used elsewhere
    is not unused)."""
    pen = _Pen(color)
    out: list[str] = []
    title = f"{report['diagram']} · {report['title']}"
    if not report["styled"]:
        return f"{pen.bold(title)}\n  {pen.dim('no stylesheet or inline css')}\n"
    sheets = ", ".join(_origin(s["origin"], None, base) + (" (theme)" if s["theme"] else "")
                       for s in report["sheets"]) or "inline css only"
    out.append(f"{pen.bold(title)}  {pen.dim('cascade: ' + sheets)}")
    labels = {e["key"]: element_label(e) for e in report["elements"]}
    quiet: list[str] = []
    for e in report["elements"]:
        if keys is not None and e["key"] not in keys:
            continue
        if not e["trace"]:
            quiet.append(labels[e["key"]])
            continue
        kind = f" [{e['kinds'][0]}]" if e["kinds"] and e["type"] == "node" else ""
        name = e["attrs"].get("label")
        out.append("")
        out.append(f"  {pen.bold(labels[e['key']])}{pen.dim(kind)}" + (f"  {pen.dim(repr(name))}" if name else ""))
        computed = e["styles"].get("", {})
        if computed:
            vals = "  ".join(f"{pen.prop(k)} {pen.swatches(_fmt(v))}" for k, v in computed.items())
            out.append(f"    {pen.dim('computed')}  {vals}")
        for pe in ("", "title", "body", "label"):
            t = e["trace"].get(pe)
            if not t:
                continue
            if pe:
                if not t["decls"]:
                    continue  # inherited-only pseudo-elements repeat the element's own values
                pv = "  ".join(f"{pen.prop(k)} {pen.swatches(_fmt(v))}" for k, v in e["styles"].get(pe, {}).items())
                out.append(f"    {pen.bold('::' + pe)}  {pv}")
            _section(out, pen, t, base, labels, "      " if pe else "    ")
    if quiet:
        out.append("")
        out.append(f"  {pen.dim(f'{len(quiet)} element(s) without declarations: ' + ', '.join(quiet))}")
    shown = report["unused"] if unused_selectors else []
    if shown or report["warnings"]:
        out.append("")
    for u in shown:
        out.append(f"  {pen.dim('info: unused selector')} {pen.sel(u['selector'])} "
                   f"{pen.dim(_origin(u['origin'], u['line'], base))}")
    for w in report["warnings"]:
        out.append(f"  {pen.warn('warning:')} {w}")
    return "\n".join(out) + "\n"


def unused(reports: list[dict]) -> list[dict]:
    """Selectors unused in every checked diagram whose cascade includes their stylesheet."""
    seen: dict[tuple, int] = {}
    users: dict[str, int] = {}
    for r in reports:
        for s in r["sheets"]:
            users[s["origin"]] = users.get(s["origin"], 0) + 1
        for u in {(u["origin"], u["line"], u["selector"]) for u in r["unused"]}:
            seen[u] = seen.get(u, 0) + 1
    return [{"origin": o, "line": ln, "selector": s} for (o, ln, s), n in sorted(seen.items(), key=lambda x: (x[0][0], x[0][1]))
            if n == users.get(o)]

