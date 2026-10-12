"""CSS-like styling: stylesheets with selectors, cascade and custom properties.

``tinycss2`` tokenizes the stylesheet; selectors, the cascade and the property table are spinagram's.
Supported selectors: type (``node``, ``edge``, ``group``, ``region``, ``lane``, ``diagram`` and every node
kind such as ``state`` or ``decision``), ``*``, ``.class``, ``#id``, ``[attr]``, ``[attr=value]``,
descendant and ``>`` combinators, selector lists, ``:first-child``, ``:last-child``, ``:not(...)`` and the
pseudo-elements ``::title``, ``::body``, ``::label``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import tinycss2


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
            if name not in ("first-child", "last-child"):
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
