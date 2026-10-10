"""Facts: numbers in diagrams that stay traceable to their source.

A facts file is JSON — ``{"facts": [...]}``, a list, or ``{id: fact}`` — where each fact has
``id``, ``label``, ``format`` (int | pct | float | brl | text), optional ``decimals`` and either a
``value`` or a ``source.formula`` over ``source.inputs`` (derived). ``source`` is free-form;
these keys are shown to reviewers when present: ``system``, ``query``, ``review_url``,
``script``, ``data``, ``computed_at``, ``computation``, ``classification``, ``note``, ``formula``.

In specs, write ``{{fact_id}}`` (or ``{{fact_id|pct1}}`` to override the format) in any text.
The rendered value is recorded on the element; backends expose the provenance (SVG tooltip,
PowerPoint speaker notes, ``fontes.md`` review file).
"""
from __future__ import annotations

import ast
import json
import operator
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*(?:\|\s*([a-z]+)(\d*)\s*)?\}\}")
REVIEW_KEYS = ("system", "query", "review_url", "filter", "classification", "script", "data", "raw_data",
               "computed_at", "computation", "formula", "note")
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.USub: operator.neg, ast.Pow: operator.pow}


class FactError(KeyError):
    pass


@dataclass
class FactRegistry:
    facts: dict[str, dict[str, Any]]
    path: Path | None = None
    locale: str = "en"
    _cache: dict[str, float] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path, locale: str | None = None) -> "FactRegistry":
        p = Path(path)
        raw = json.loads(p.read_text(encoding="utf-8"))
        items = raw.get("facts", raw) if isinstance(raw, dict) else raw
        if isinstance(items, dict) and "id" not in next(iter(items.values()), {}):
            items = [{"id": k, **v} for k, v in items.items()]
        facts = {f["id"]: f for f in (items.values() if isinstance(items, dict) else items)}
        meta = raw.get("meta", {}) if isinstance(raw, dict) else {}
        return cls(facts, p, locale or meta.get("locale") or "en")

    # values -------------------------------------------------------------------
    def get(self, fid: str) -> dict[str, Any]:
        if fid not in self.facts:
            raise FactError(f"unknown fact {fid!r} in {self.path}")
        return self.facts[fid]

    def value(self, fid: str) -> Any:
        if fid in self._cache:
            return self._cache[fid]
        f = self.get(fid)
        if f.get("value") is not None:
            v = f["value"]
        else:
            src = f.get("source") or {}
            if not src.get("formula"):
                raise FactError(f"fact {fid!r} has neither value nor formula")
            v = self._eval(src["formula"], {i: self.value(i) for i in src.get("inputs", [])})
        self._cache[fid] = v
        return v

    @staticmethod
    def _eval(expr: str, names: dict[str, Any]) -> float:
        def ev(n):
            if isinstance(n, ast.Expression):
                return ev(n.body)
            if isinstance(n, ast.Constant):
                return n.value
            if isinstance(n, ast.Name):
                return names[n.id]
            if isinstance(n, ast.BinOp):
                return _OPS[type(n.op)](ev(n.left), ev(n.right))
            if isinstance(n, ast.UnaryOp):
                return _OPS[type(n.op)](ev(n.operand))
            raise FactError(f"unsupported formula element in {expr!r}")
        return ev(ast.parse(expr, mode="eval"))

    # formatting ---------------------------------------------------------------
    def _num(self, v: float, decimals: int) -> str:
        s = f"{v:,.{decimals}f}"
        if self.locale.lower().startswith("pt"):
            s = s.replace(",", "§").replace(".", ",").replace("§", ".")
        return s

    def display(self, fid: str, fmt: str | None = None, decimals: int | None = None) -> str:
        f = self.get(fid)
        v = self.value(fid)
        fmt = fmt or f.get("format", "text")
        if decimals is None:
            decimals = f.get("decimals", 0 if fmt in ("int", "pct") else 1)
        fmt = {"brl_mi": "brl"}.get(fmt, fmt)
        if fmt == "raw":  # plain machine number, e.g. for CSS widths
            return f"{v:g}" if isinstance(v, (int, float)) else str(v)
        if fmt == "hours" and isinstance(v, (int, float)):
            return self._num(round(v), 0) + " h"
        if not isinstance(v, (int, float)) or fmt == "text":
            return str(v)
        if fmt == "int":
            return self._num(round(v), 0)
        if fmt == "pct":
            return self._num(v, decimals) + "%"
        if fmt == "brl":
            if abs(v) >= 1e6:
                return "R$ " + self._num(v / 1e6, 1) + " mi"
            return "R$ " + self._num(v, 0)
        return self._num(v, decimals)

    def substitute(self, text: str) -> tuple[str, list[str]]:
        """Replace ``{{id}}`` placeholders; return the text and the fact ids used."""
        used: list[str] = []

        def rep(m: re.Match) -> str:
            fid, fmt, dec = m.group(1), m.group(2), m.group(3)
            used.append(fid)
            return self.display(fid, fmt, int(dec) if dec else None)
        return PLACEHOLDER.sub(rep, text), used

    # review -------------------------------------------------------------------
    def review(self, fid: str) -> dict[str, Any]:
        f = self.get(fid)
        src = f.get("source") or {}
        out = {"id": fid, "label": f.get("label", fid), "display": self.display(fid)}
        out.update({k: src[k] for k in REVIEW_KEYS if src.get(k)})
        if src.get("inputs"):
            out["inputs"] = [self.review(i) for i in src["inputs"]]
        return out

    def tooltip(self, fid: str) -> str:
        r = self.review(fid)
        parts = [f"{r['label']}: {r['display']}"]
        for k in ("system", "query", "classification", "formula", "computed_at"):
            if r.get(k):
                parts.append(f"{k}: {r[k]}")
        return "\n".join(parts)


def has_placeholders(text: Any) -> bool:
    return isinstance(text, str) and bool(PLACEHOLDER.search(text))


def sources_markdown(entries: list[tuple[str, str, list[dict]]]) -> str:
    """Review document: per diagram, each fact with value, query, link and computation."""
    lines = ["# Fontes dos números", "",
             "Cada número exibido nos slides, com a consulta que o gerou e onde foi calculado.", ""]
    for did, title, reviews in entries:
        if not reviews:
            continue
        lines += [f"## {did} · {title}", ""]
        for r in reviews:
            lines += _review_md(r, 0)
        lines.append("")
    return "\n".join(lines)


def _review_md(r: dict, depth: int) -> list[str]:
    pad = "  " * depth
    out = [f"{pad}- **{r['display']}** — {r['label']} (`{r['id']}`)"]
    for k in ("system", "query", "filter", "classification", "formula", "computed_at", "computation", "data",
              "raw_data", "note"):
        if r.get(k):
            val = f"`{r[k]}`" if k in ("query", "formula", "computation", "computed_at", "data", "raw_data") else r[k]
            out.append(f"{pad}  - {k}: {val}")
    if r.get("review_url"):
        out.append(f"{pad}  - revisar: <{r['review_url']}>")
    for i in r.get("inputs", []):
        out += _review_md(i, depth + 1)
    return out


def render_html(html: str, reg: FactRegistry) -> tuple[str, list[str]]:
    """Resolve ``{{fact}}`` in an HTML page: value wrapped in a span with the provenance tooltip."""
    import html as _html

    used: list[str] = []

    def rep(m: re.Match) -> str:
        fid, fmt, dec = m.group(1), m.group(2), m.group(3)
        if fid not in used:
            used.append(fid)
        value = reg.display(fid, fmt, int(dec) if dec else None)
        if fmt == "raw":
            return value
        return (f'<span class="dk-fact" data-fact="{fid}" title="{_html.escape(reg.tooltip(fid), quote=True)}">'
                f'{_html.escape(value)}</span>')
    return PLACEHOLDER.sub(rep, html), used
