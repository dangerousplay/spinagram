"""Content-driven size for nodes that have no ``w``/``h``."""
from __future__ import annotations

from ..model import Node
from ..text import measure, wrap_paragraphs
from ..theme import Theme


def _lines(n: Node) -> tuple[list[str], list[str]]:
    title = n.title if isinstance(n.title, list) else ([n.title] if n.title else [])
    body = n.lines if n.lines is not None else ([n.text] if n.text else [])
    return [str(t) for t in title], [str(b) for b in body]


def auto_size(n: Node, theme: Theme) -> tuple[float, float]:
    """Smallest box (within ``defaults.node.auto``) that fits the wrapped title/body and the icon."""
    nd, auto = theme.defaults("node"), theme.defaults("node").get("auto") or {}
    min_w, max_w, min_h = auto.get("min_w", 220), auto.get("max_w", 360), auto.get("min_h", 96)
    pad = nd.get("padding", 22)
    ts, bs = n.title_size or nd.get("title_size", 24), n.body_size or nd.get("body_size", 18)
    tf, bf = theme.font("heading", 700, ts), theme.font("body", 400, bs)
    title, body = _lines(n)
    if n.kind == "diamond":
        inner = max([measure(t, tf) for t in title] or [0])
        side = max(min_h * 1.6, inner / theme.defaults("diamond").get("text_width", 0.72) + 2 * pad)
        return n.w or side, n.h or side * 0.75
    center = n.align == "center"
    isz = n.icon_size or nd.get("icon_size_center" if center else "icon_size", 40 if center else 44) if n.icon else 0
    offset = 0 if center or not isz else isz + nd.get("icon_gap", 14)
    natural = max([measure(t, tf) for t in title] + [measure(b, bf) for b in body] + [0])
    w = n.w or min(max_w, max(min_w, natural + 2 * pad + offset + 4))
    avail = w - 2 * pad - offset
    th = len(wrap_paragraphs(title, tf, avail)) * ts * nd.get("title_leading", 1.15) if title else 0
    bh = len(wrap_paragraphs(body, bf, avail)) * bs * nd.get("body_leading", 1.32) if body else 0
    text_h = th + bh + (nd.get("title_body_gap", 10) if th and bh else 0)
    top = 16 + isz - 12 if center and isz else 0
    h = n.h or max(min_h, text_h + top + 2 * pad, (isz + 2 * pad) if not center else 0)
    return w, h
