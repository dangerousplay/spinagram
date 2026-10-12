"""CSS-like styling: stylesheets with selectors, cascade and custom properties.

``tinycss2`` tokenizes the stylesheet; selectors, the cascade and the property table are spinagram's.
Supported selectors: type (``node``, ``edge``, ``group``, ``region``, ``lane``, ``diagram`` and every node
kind such as ``state`` or ``decision``), ``*``, ``.class``, ``#id``, ``[attr]``, ``[attr=value]``,
descendant and ``>`` combinators, selector lists, ``:first-child``, ``:last-child``, ``:not(...)`` and the
pseudo-elements ``::title``, ``::body``, ``::label``.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

import tinycss2
from PIL import ImageColor


# parsing ----------------------------------------------------------------------------------------
@dataclass
class CssError:
    origin: str
    line: int
    column: int
    message: str

    def __str__(self) -> str:
        return f"{self.origin}:{self.line}:{self.column}: {self.message}"


@dataclass
class Decl:
    name: str
    value: str
    important: bool = False
    line: int = 0


@dataclass
class Compound:
    type: str | None = None                 # None or "*" = any
    id: str | None = None
    classes: list[str] = field(default_factory=list)
    attrs: list[tuple[str, str | None]] = field(default_factory=list)  # (name, value or None for presence)
    pseudos: list[Any] = field(default_factory=list)   # "first-child" | "last-child" | ("not", [Selector])


@dataclass
class Selector:
    text: str
    parts: list[tuple[str, Compound]]       # (combinator before it: "" | " " | ">", compound), left to right
    pseudo_element: str | None = None

    @property
    def specificity(self) -> tuple[int, int, int]:
        a = b = c = 0
        for _, comp in self.parts:
            a += 1 if comp.id else 0
            b += len(comp.classes) + len(comp.attrs)
            c += 1 if comp.type not in (None, "*") else 0
            for p in comp.pseudos:
                if isinstance(p, tuple):  # :not(list) takes its most specific argument
                    sa, sb, sc = max((s.specificity for s in p[1]), default=(0, 0, 0))
                    a, b, c = a + sa, b + sb, c + sc
                else:
                    b += 1
        return (a, b, c + (1 if self.pseudo_element else 0))


@dataclass
class Rule:
    selectors: list[Selector]
    decls: list[Decl]
    origin: str = "<css>"
    order: int = 0
    line: int = 0


_IDENT = r"-?[A-Za-z_][\w-]*"
_TOKEN = re.compile(rf"""
    (?P<ws>\s+) | (?P<child>>) | (?P<comma>,) |
    (?P<pe>::{_IDENT}) | (?P<not>:not\() | (?P<pc>:{_IDENT}) |
    (?P<id>\#{_IDENT}) | (?P<cls>\.{_IDENT}) |
    (?P<attr>\[\s*{_IDENT}\s*(?:=\s*(?:"[^"]*"|'[^']*'|[^\]\s]+)\s*)?\]) |
    (?P<type>{_IDENT}|\*) | (?P<close>\))
""", re.X)


class _SelectorError(ValueError):
    pass


def _split_top(text: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def parse_selectors(text: str) -> list[Selector]:
    return [_parse_one(p.strip()) for p in _split_top(text) if p.strip()] or _fail(text)


def _fail(text: str):
    raise _SelectorError(f"empty selector {text!r}")


def _parse_one(text: str) -> Selector:
    pos, parts, comb, comp, pe = 0, [], "", None, None
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise _SelectorError(f"cannot parse selector {text!r} near {text[pos:pos + 12]!r}")
        kind, tok = m.lastgroup, m.group()
        pos = m.end()
        if kind in ("ws", "child"):
            if comp is not None:
                parts.append((comb, comp))
                comp = None
                comb = " "
            if kind == "child":
                comb = ">"
            continue
        if pe:
            raise _SelectorError(f"pseudo-element must end the selector: {text!r}")
        if comp is None:
            comp = Compound()
        if kind == "type":
            comp.type = tok
        elif kind == "id":
            comp.id = tok[1:]
        elif kind == "cls":
            comp.classes.append(tok[1:])
        elif kind == "attr":
            body = tok[1:-1].strip()
            name, _, val = body.partition("=")
            val = val.strip()
            if val[:1] in "\"'" and val:
                val = val[1:-1]
            comp.attrs.append((name.strip(), val if "=" in body else None))
        elif kind == "pc":
            name = tok[1:]
            if name not in ("first-child", "last-child", "root"):
                raise _SelectorError(f"unsupported pseudo-class :{name}")
            comp.pseudos.append(name)
        elif kind == "not":
            depth, start = 1, pos
            while pos < len(text) and depth:
                depth += {"(": 1, ")": -1}.get(text[pos], 0)
                pos += 1
            if depth:
                raise _SelectorError(f"unclosed :not( in {text!r}")
            comp.pseudos.append(("not", parse_selectors(text[start:pos - 1])))
        elif kind == "pe":
            name = tok[2:]
            if name not in ("title", "body", "label"):
                raise _SelectorError(f"unsupported pseudo-element ::{name}")
            pe = name
        else:
            raise _SelectorError(f"unexpected {tok!r} in selector {text!r}")
    if comp is not None:
        parts.append((comb, comp))
    if not parts:
        if pe:  # "::label" alone → any element
            parts.append(("", Compound()))
        else:
            raise _SelectorError(f"empty selector {text!r}")
    parts[0] = ("", parts[0][1])
    return Selector(text, parts, pe)


def parse(text: str, origin: str = "<css>", order_base: int = 0) -> tuple[list[Rule], list[CssError]]:
    """Rules in source order and the errors met (broken rules are skipped, the rest kept)."""
    rules: list[Rule] = []
    errors: list[CssError] = []
    for node in tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True):
        if node.type == "error":
            errors.append(CssError(origin, node.source_line, node.source_column, node.message))
            continue
        if node.type == "at-rule":
            errors.append(CssError(origin, node.source_line, node.source_column,
                                   f"unsupported at-rule @{node.at_keyword}"))
            continue
        prelude = tinycss2.serialize(node.prelude).strip()
        try:
            selectors = parse_selectors(prelude)
        except _SelectorError as exc:
            errors.append(CssError(origin, node.source_line, node.source_column, f"{exc} (rule {prelude!r} skipped)"))
            continue
        decls = []
        for d in tinycss2.parse_declaration_list(node.content, skip_comments=True, skip_whitespace=True):
            if d.type == "error":
                errors.append(CssError(origin, d.source_line, d.source_column, d.message))
            elif d.type == "declaration":
                decls.append(Decl(d.lower_name, tinycss2.serialize(d.value).strip(), d.important, d.source_line))
        rules.append(Rule(selectors, decls, origin, order_base + len(rules), node.source_line))
    return rules, errors


# matching ---------------------------------------------------------------------------------------
@dataclass(eq=False)
class El:
    """An element of the style tree: the diagram, a group, a node or an edge."""
    type: str
    kinds: list[str] = field(default_factory=list)   # extra type names it answers to (node kind)
    id: str | None = None
    classes: list[str] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)
    parent: "El | None" = None
    inline: str | None = None
    children: list["El"] = field(default_factory=list)
    key: str | None = None

    def __post_init__(self) -> None:
        if self.parent is not None:
            self.parent.children.append(self)

    def names(self) -> set[str]:
        return {self.type, *self.kinds}


def _match_compound(comp: Compound, el: El) -> bool:
    if comp.type not in (None, "*") and comp.type not in el.names():
        return False
    if comp.id is not None and comp.id != el.id:
        return False
    if any(c not in el.classes for c in comp.classes):
        return False
    for name, val in comp.attrs:
        have = el.attrs.get(name)
        if have is None or (val is not None and str(have) != val):
            return False
    for p in comp.pseudos:
        sibs = el.parent.children if el.parent is not None else [el]
        if p == "first-child" and sibs[0] is not el:
            return False
        if p == "last-child" and sibs[-1] is not el:
            return False
        if p == "root" and el.parent is not None:
            return False
        if isinstance(p, tuple) and any(matches(s, el) for s in p[1]):
            return False
    return True


def matches(sel: Selector, el: El) -> bool:
    """Right-to-left match of a selector (its pseudo-element is the caller's concern)."""
    def at(i: int, node: El | None) -> bool:
        if node is None or not _match_compound(sel.parts[i][1], node):
            return False
        if i == 0:
            return True
        comb = sel.parts[i][0]
        if comb == ">":
            return at(i - 1, node.parent)
        anc = node.parent
        while anc is not None:
            if at(i - 1, anc):
                return True
            anc = anc.parent
        return False

    return at(len(sel.parts) - 1, el)


# values -----------------------------------------------------------------------------------------
INHERITED = {"color", "font-family", "font-size", "font-weight", "font-style"}
MARKERS = {"none", "arrow", "open-arrow", "diamond", "open-diamond", "circle", "bar"}


class CssValueError(ValueError):
    pass


def _num(v: str) -> float:
    v = v.strip()
    if v.endswith("px"):
        v = v[:-2]
    return float(v)


def _frac(v: str) -> float:
    v = v.strip()
    return float(v[:-1]) / 100 if v.endswith("%") else float(v)


def _split_ws(v: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in v:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch.isspace() and depth == 0:
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def _colour(v: str, theme) -> tuple[str, float]:
    """→ (#RRGGBB, alpha). Hex, rgb()/rgba(), CSS names, or a theme colour token."""
    v = v.strip()
    m = re.fullmatch(r"rgba?\(([^)]*)\)", v)
    if m:
        parts = [p.strip() for p in re.split(r"[,\s/]+", m.group(1)) if p.strip()]
        rgb = [round(float(p[:-1]) * 2.55) if p.endswith("%") else int(float(p)) for p in parts[:3]]
        alpha = _frac(parts[3]) if len(parts) > 3 else 1.0
        return "#{:02X}{:02X}{:02X}".format(*rgb), alpha
    if v.startswith("#"):
        h = v[1:]
        if not re.fullmatch(r"[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8}", h):
            raise KeyError(v)  # reported as "cannot resolve colour"
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        alpha = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return "#" + h[:6].upper(), alpha
    if v.lower() in ImageColor.colormap:
        r, g, b = ImageColor.getrgb(v.lower())[:3]
        return f"#{r:02X}{g:02X}{b:02X}", 1.0
    return theme.color(v), 1.0  # raises KeyError for unknown tokens


def _shadow(v: str, theme):
    if v.strip() == "none":
        return None
    toks = _split_ws(v)
    nums = [t for t in toks if re.fullmatch(r"-?[\d.]+(px)?", t)]
    rest = [t for t in toks if t not in nums]
    ox, oy, blur = (_num(x) for x in (nums + ["0", "0", "0"])[:3])
    col, alpha = _colour(rest[0], theme) if rest else ("#000000", 0.35)
    return (ox, oy, blur, col, alpha)


def _weight(v: str) -> int:
    v = v.strip().lower()
    return {"normal": 400, "bold": 700, "lighter": 300, "bolder": 800}.get(v) or int(v)


def _keyword(allowed):
    def parse(v: str, theme=None) -> str:
        v = v.strip().lower()
        if v not in allowed:
            raise ValueError(f"expected one of {sorted(allowed)}")
        return v
    return parse


def _length(v: str, theme=None) -> float:
    x = _num(v)
    if x < 0:
        raise ValueError("negative values are not allowed")
    return x


PROPS = {
    "fill": lambda v, t: _colour(v, t)[0],
    "stroke": lambda v, t: _colour(v, t)[0],
    "color": lambda v, t: _colour(v, t)[0],
    "stroke-width": _length,
    "border-radius": _length,
    "font-size": _length,
    "stroke-dasharray": lambda v, t: [] if v.strip() == "none" else [_length(x) for x in re.split(r"[\s,]+", v.strip())],
    "opacity": lambda v, t: max(0.0, min(1.0, _frac(v))),
    "fill-opacity": lambda v, t: max(0.0, min(1.0, _frac(v))),
    "box-shadow": _shadow,
    "font-weight": lambda v, t: _weight(v),
    "font-style": _keyword({"normal", "italic"}),
    "font-family": lambda v, t: v.strip().strip("'\""),
    "marker-start": _keyword(MARKERS),
    "marker-end": _keyword(MARKERS),
}
COLOUR_PROPS = {"fill", "stroke", "color", "box-shadow"}


def _substitute(value: str, custom: dict[str, str]) -> str:
    """Replace var(--x[, fallback]); an unknown --x falls back to the theme token ``x``.
    Fallbacks may contain functions (``var(--x, rgb(1, 2, 3))``)."""
    for _ in range(8):  # nested var()
        i = value.find("var(")
        if i < 0:
            break
        depth, j = 1, i + 4
        while j < len(value) and depth:
            depth += {"(": 1, ")": -1}.get(value[j], 0)
            j += 1
        inner = value[i + 4:j - 1]
        name, _, fb = inner.partition(",")
        name = name.strip()
        rep = custom.get(name) if name in custom else (fb.strip() if fb.strip() else name[2:])
        value = value[:i] + rep + value[j:]
    return value


def compute(root: El, rules: list[Rule], theme, warnings: list[str] | None = None,
            trace: dict | None = None) -> dict[El, dict[str, dict]]:
    """Computed style per element and pseudo-element (``""``, ``"title"``, ``"body"``, ``"label"``).

    With ``trace`` (a dict), also records why: ``trace[el][pseudo] = {"decls": [...], "inherited": [...]}``.
    Each declaration entry has ``property``, ``value``, ``resolved`` (after ``var()``), ``origin``, ``line``,
    ``selector``, ``specificity``, ``important`` and ``status`` (``applied``, ``overridden``, ``invalid`` or
    ``unknown``, the last two with a ``message``), in cascade order (the winner of a property comes last).
    Inherited entries have ``property``, ``value`` and ``from`` (the key of the element that set it)."""
    warnings = warnings if warnings is not None else []
    out: dict[El, dict[str, dict]] = {}
    warned: set[tuple] = set()

    def warn(msg: str) -> None:
        if msg not in warned:
            warned.add(msg)
            warnings.append(msg)

    def declared(el: El, pseudo: str | None) -> list[tuple[tuple, Decl, Rule | None, Selector | None]]:
        found = []
        for r in rules:
            for sel in r.selectors:
                if sel.pseudo_element == pseudo and matches(sel, el):
                    for i, d in enumerate(r.decls):
                        found.append(((2 if d.important else 0, sel.specificity, r.order, i), d, r, sel))
        if el.inline and pseudo is None:
            for i, d in enumerate(_inline(el.inline)):
                found.append(((3 if d.important else 1, (0, 0, 0), 0, i), d, None, None))
        found.sort(key=lambda f: f[0])
        return found

    def resolve(el: El, pseudo: str | None, parent_vals: dict, parent_custom: dict,
                parent_src: dict) -> tuple[dict, dict, dict]:
        decls = declared(el, pseudo)
        custom = dict(parent_custom)
        for _, d, _, _ in decls:
            if d.name.startswith("--"):
                custom[d.name] = d.value
        vals = {k: v for k, v in parent_vals.items() if k in INHERITED}
        src = {k: v for k, v in parent_src.items() if k in vals}
        rec: list[dict] = []
        for _, d, r, sel in decls:
            where = f"{r.origin}:{d.line}" if r else f"{el.key or el.id}: inline css"
            entry = {"property": d.name, "value": d.value, "resolved": d.value,
                     "origin": r.origin if r else "inline", "line": d.line if r else None,
                     "selector": sel.text if sel else None, "specificity": list(sel.specificity) if sel else None,
                     "important": d.important, "status": "applied"}
            rec.append(entry)
            if d.name.startswith("--"):
                continue
            if d.name not in PROPS:
                near = difflib.get_close_matches(d.name, list(PROPS), n=1)
                hint = f" (did you mean '{near[0]}'?)" if near else ""
                warn(f"{where}: unknown property '{d.name}'{hint}")
                entry.update(status="unknown", message=f"unknown property{hint}")
                continue
            raw = _substitute(d.value, custom)
            entry["resolved"] = raw
            try:
                vals[d.name] = PROPS[d.name](raw, theme)
                src[d.name] = el.key or el.id
            except KeyError:
                if d.name in COLOUR_PROPS:
                    who = sel.text if sel else (el.key or el.id)
                    raise CssValueError(f"{where}: {who}: cannot resolve colour {raw!r}") from None
                warn(f"{where}: invalid value {raw!r} for '{d.name}'")
                entry.update(status="invalid", message=f"invalid value {raw!r}")
            except ValueError as exc:
                warn(f"{where}: '{d.name}: {raw}' ignored — {exc}")
                entry.update(status="invalid", message=str(exc))
        if trace is not None:
            winner: dict[str, dict] = {}
            for entry in rec:
                if entry["status"] == "applied":
                    if entry["property"] in winner:
                        winner[entry["property"]]["status"] = "overridden"
                    winner[entry["property"]] = entry
            inherited = [{"property": k, "value": _jsonable(v), "from": src.get(k)}
                         for k, v in vals.items() if k not in winner and k in parent_vals]
            trace.setdefault(el, {})[pseudo or ""] = {"decls": rec, "inherited": inherited}
        return vals, custom, src

    def walk(el: El, parent_vals: dict, parent_custom: dict, parent_src: dict) -> None:
        vals, custom, src = resolve(el, None, parent_vals, parent_custom, parent_src)
        out[el] = {"": vals}
        for pe in ("title", "body", "label"):
            out[el][pe] = resolve(el, pe, vals, custom, src)[0]
        for c in el.children:
            walk(c, vals, custom, src)

    walk(root, {}, {}, {})
    return out


def _jsonable(v: Any) -> Any:
    return [_jsonable(x) for x in v] if isinstance(v, (list, tuple)) else v


def _inline(text: str) -> list[Decl]:
    decls = []
    for d in tinycss2.parse_declaration_list(text, skip_comments=True, skip_whitespace=True):
        if d.type == "declaration":
            decls.append(Decl(d.lower_name, tinycss2.serialize(d.value).strip(), d.important, 0))
    return decls


# diagrams ---------------------------------------------------------------------------------------
def _classes(cls: str | None, style: str | None) -> list[str]:
    return (cls or "").split() + ([style] if style else [])


def tree(d) -> tuple[El, dict[str, El]]:
    """Style tree of a diagram: diagram → groups (``group``/``region``/``lane``) → nodes; edges under the root."""
    root = El("diagram", id=d.id, key="diagram")
    keys: dict[str, El] = {"diagram": root}
    by_group = {g.id: g for g in d.groups}
    nodes = {n.id: n for n in d.nodes}
    child_of = {c for g in d.groups for c in g.children}

    def add(item_id: str, parent: El) -> None:
        if item_id in by_group:
            g = by_group[item_id]
            typ = "lane" if g.style == "lane" else ("region" if g.region else "group")
            kinds = ["group"] + ([g.region] if g.region else [])
            el = El(typ, kinds, g.id, _classes(g.cls, g.style),
                    {k: v for k, v in (("label", g.label), ("style", g.style)) if v}, parent, g.css, key=f"group:{g.id}")
            keys[el.key] = el
            for c in g.children:
                add(c, el)
        elif item_id in nodes:
            n = nodes[item_id]
            title = " ".join(n.title) if isinstance(n.title, list) else n.title
            attrs = {k: v for k, v in (("kind", n.kind), ("label", title), ("icon", n.icon), ("style", n.style)) if v}
            el = El("node", [n.kind], n.id, _classes(n.cls, n.style), attrs, parent, n.css, key=f"node:{n.id}")
            keys[el.key] = el

    for g in d.groups:
        if g.id not in child_of:
            add(g.id, root)
    for n in d.nodes:
        if n.id not in child_of:
            add(n.id, root)
    for i, e in enumerate(d.edges):
        attrs = {"from": str(e.src).partition(".")[0], "to": str(e.dst).partition(".")[0]}
        if e.label:
            attrs["label"] = e.label
        el = El("edge", [], None, _classes(e.cls, None), attrs, root, e.css, key=f"edge:{i}")
        keys[el.key] = el
    return root, keys


def _sheet_text(sheet: str, base_dir) -> tuple[str, str]:
    """(text, origin) for a stylesheet given as CSS text or a path."""
    from pathlib import Path

    if "{" in sheet:
        return sheet, "<css>"
    p = Path(sheet)
    if not p.is_absolute() and base_dir is not None and (Path(base_dir) / p).exists():
        p = Path(base_dir) / p
    return p.read_text(encoding="utf-8"), str(p)


def sheets_for(d, theme) -> list[tuple[str, str]]:
    """Stylesheets in cascade order: theme ``theme.css``, folder defaults, the diagram's own."""
    out = []
    for path in getattr(theme, "stylesheets", lambda: [])():
        out.append((path.read_text(encoding="utf-8"), str(path)))
    for sheet in d.stylesheets:
        out.append(_sheet_text(sheet, d.base_dir))
    if d.css:
        out.append((d.css, f"{d.id} css"))
    return out


def styles(d, theme) -> tuple[dict[str, dict[str, dict]], list[str]]:
    """Computed styles keyed ``node:<id>``, ``edge:<index>``, ``group:<id>``, ``diagram``, and warnings.
    Empty when the diagram uses no stylesheet and no inline css."""
    sheets = sheets_for(d, theme)
    inline = any(x.css for x in (*d.nodes, *d.edges, *d.groups))
    if not sheets and not inline:
        return {}, []
    rules: list[Rule] = []
    warnings: list[str] = []
    for text, origin in sheets:
        rs, errs = parse(text, origin, order_base=len(rules))
        rules += rs
        warnings += [str(e) for e in errs]
    root, keys = tree(d)
    comp = compute(root, rules, theme, warnings)
    return {k: comp[el] for k, el in keys.items()}, warnings


def prepare(d, theme):
    """Resolve the cascade once: a copy of ``d`` with computed styles in ``meta["css"]`` and title/body
    font sizes written into the nodes (so automatic sizing sees them). ``d`` itself when unstyled."""
    import copy

    if "css" in d.meta:
        return d
    comp, warnings = styles(d, theme)
    if not comp and not warnings:
        return d
    d = copy.deepcopy(d)
    d.meta["css"] = comp
    d.meta["css_warnings"] = warnings
    for n in d.nodes:
        st = comp.get(f"node:{n.id}") or {}
        if "font-size" in st.get("title", {}):
            n.title_size = st["title"]["font-size"]
        if "font-size" in st.get("body", {}):
            n.body_size = st["body"]["font-size"]
    return d
