"""Geometry of the flow, activity and state symbols, defined once for the scene and every backend.

Each kind maps to drawable parts in absolute coordinates (SVG path syntax restricted to absolute
``M``, ``L``, ``C`` and ``Z`` so every backend can convert them), the box its text must stay inside,
an optional fixed size (pseudostates are not sized by text) and how PowerPoint should draw it
(a preset autoshape name, ``"group"`` for multi-part symbols, or ``"freeform"``).

Paint of a part: ``shape`` uses the node style's fill and stroke, ``solid`` is filled with the stroke
colour (start dots, fork bars), ``stroke`` is an outline only (rings, inner lines).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

K = 0.5523  # cubic Bézier circle constant

Box = tuple[float, float, float, float]


@dataclass
class Part:
    d: str
    paint: str = "shape"  # shape | solid | stroke


@dataclass
class Subpath:
    start: tuple[float, float]
    segments: list[tuple[str, list[tuple[float, float]]]] = field(default_factory=list)  # ("L"|"C", points)
    closed: bool = False


@dataclass
class _Spec:
    parts: Callable[[float, float, float, float], list[Part]]
    text: Callable[[float, float, float, float], Box]
    size: tuple[float, float] | None = None
    pptx: str = "freeform"


def _f(v: float) -> str:
    return f"{round(v, 2):g}"


def _poly(pts, close: bool = True) -> str:
    d = "M " + " L ".join(f"{_f(x)} {_f(y)}" for x, y in pts)
    return d + (" Z" if close else "")


def _ellipse(cx: float, cy: float, rx: float, ry: float) -> str:
    kx, ky = rx * K, ry * K
    return (f"M {_f(cx - rx)} {_f(cy)} "
            f"C {_f(cx - rx)} {_f(cy - ky)} {_f(cx - kx)} {_f(cy - ry)} {_f(cx)} {_f(cy - ry)} "
            f"C {_f(cx + kx)} {_f(cy - ry)} {_f(cx + rx)} {_f(cy - ky)} {_f(cx + rx)} {_f(cy)} "
            f"C {_f(cx + rx)} {_f(cy + ky)} {_f(cx + kx)} {_f(cy + ry)} {_f(cx)} {_f(cy + ry)} "
            f"C {_f(cx - kx)} {_f(cy + ry)} {_f(cx - rx)} {_f(cy + ky)} {_f(cx - rx)} {_f(cy)} Z")


def _rrect(x: float, y: float, w: float, h: float, r: float) -> str:
    r = max(0.0, min(r, w / 2, h / 2))
    if r == 0:
        return _poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
    k = r * (1 - K)
    return (f"M {_f(x + r)} {_f(y)} L {_f(x + w - r)} {_f(y)} "
            f"C {_f(x + w - k)} {_f(y)} {_f(x + w)} {_f(y + k)} {_f(x + w)} {_f(y + r)} "
            f"L {_f(x + w)} {_f(y + h - r)} "
            f"C {_f(x + w)} {_f(y + h - k)} {_f(x + w - k)} {_f(y + h)} {_f(x + w - r)} {_f(y + h)} "
            f"L {_f(x + r)} {_f(y + h)} "
            f"C {_f(x + k)} {_f(y + h)} {_f(x)} {_f(y + h - k)} {_f(x)} {_f(y + h - r)} "
            f"L {_f(x)} {_f(y + r)} "
            f"C {_f(x)} {_f(y + k)} {_f(x + k)} {_f(y)} {_f(x + r)} {_f(y)} Z")


def _circle_in(x, y, w, h, scale: float = 1.0) -> str:
    r = min(w, h) / 2 * scale
    return _ellipse(x + w / 2, y + h / 2, r, r)


def _diamond(x, y, w, h) -> list[Part]:
    return [Part(_poly([(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]))]


def _skew(w, h) -> float:
    return min(0.2 * w, 0.4 * h)


def _wave(h) -> float:
    return h * 0.1


def _cap(h) -> float:
    return min(h * 0.12, 14.0)


def _inset(fx: float, fy: float):
    return lambda x, y, w, h: (x + w * fx, y + h * fy, w * (1 - 2 * fx), h * (1 - 2 * fy))


def _document(x, y, w, h) -> list[Part]:
    a = _wave(h)
    b = y + h - a
    d = (f"M {_f(x)} {_f(y)} L {_f(x + w)} {_f(y)} L {_f(x + w)} {_f(b)} "
         f"C {_f(x + 0.8 * w)} {_f(b - a)} {_f(x + 0.65 * w)} {_f(b - a)} {_f(x + 0.5 * w)} {_f(b)} "
         f"C {_f(x + 0.35 * w)} {_f(b + a)} {_f(x + 0.2 * w)} {_f(b + a)} {_f(x)} {_f(b)} Z")
    return [Part(d)]


def _cylinder(x, y, w, h) -> list[Part]:
    ry = _cap(h)
    cx, rx = x + w / 2, w / 2
    kx, ky = rx * K, ry * K
    top, bot = y + ry, y + h - ry
    body = (f"M {_f(x)} {_f(top)} L {_f(x)} {_f(bot)} "
            f"C {_f(x)} {_f(bot + ky)} {_f(cx - kx)} {_f(bot + ry)} {_f(cx)} {_f(bot + ry)} "
            f"C {_f(cx + kx)} {_f(bot + ry)} {_f(x + w)} {_f(bot + ky)} {_f(x + w)} {_f(bot)} "
            f"L {_f(x + w)} {_f(top)} "
            f"C {_f(x + w)} {_f(top - ky)} {_f(cx + kx)} {_f(top - ry)} {_f(cx)} {_f(top - ry)} "
            f"C {_f(cx - kx)} {_f(top - ry)} {_f(x)} {_f(top - ky)} {_f(x)} {_f(top)} Z")
    rim = (f"M {_f(x)} {_f(top)} "
           f"C {_f(x)} {_f(top + ky)} {_f(cx - kx)} {_f(top + ry)} {_f(cx)} {_f(top + ry)} "
           f"C {_f(cx + kx)} {_f(top + ry)} {_f(x + w)} {_f(top + ky)} {_f(x + w)} {_f(top)}")
    return [Part(body), Part(rim, "stroke")]


def _flow_final(x, y, w, h) -> list[Part]:
    r = min(w, h) / 2
    cx, cy = x + w / 2, y + h / 2
    q = r * 0.7071
    cross = (f"M {_f(cx - q)} {_f(cy - q)} L {_f(cx + q)} {_f(cy + q)} "
             f"M {_f(cx + q)} {_f(cy - q)} L {_f(cx - q)} {_f(cy + q)}")
    return [Part(_circle_in(x, y, w, h)), Part(cross, "stroke")]


def _predefined(x, y, w, h) -> list[Part]:
    i = min(0.1 * w, 18.0)
    lines = f"M {_f(x + i)} {_f(y)} L {_f(x + i)} {_f(y + h)} M {_f(x + w - i)} {_f(y)} L {_f(x + w - i)} {_f(y + h)}"
    return [Part(_poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])), Part(lines, "stroke")]


def _send(x, y, w, h) -> list[Part]:
    s = min(h / 2, w * 0.25)
    return [Part(_poly([(x, y), (x + w - s, y), (x + w, y + h / 2), (x + w - s, y + h), (x, y + h)]))]


def _receive(x, y, w, h) -> list[Part]:
    s = min(h / 2, w * 0.25)
    return [Part(_poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x + s, y + h / 2)]))]


def _round_text(x, y, w, h) -> Box:
    r = min(w, h) / 2
    s = r * 1.414
    return (x + w / 2 - s / 2, y + h / 2 - s / 2, s, s)


_RECT = lambda x, y, w, h: [Part(_poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)]))]  # noqa: E731
_TEXT = _inset(0.06, 0.08)

GEOMETRY: dict[str, _Spec] = {
    "terminator": _Spec(lambda x, y, w, h: [Part(_rrect(x, y, w, h, h / 2))],
                        lambda x, y, w, h: (x + h * 0.35, y, w - h * 0.7, h), pptx="FLOWCHART_TERMINATOR"),
    "process": _Spec(_RECT, _TEXT, pptx="RECTANGLE"),
    "decision": _Spec(_diamond, _inset(0.18, 0.18), pptx="DIAMOND"),
    "io": _Spec(lambda x, y, w, h: [Part(_poly([(x + _skew(w, h), y), (x + w, y), (x + w - _skew(w, h), y + h),
                                                 (x, y + h)]))],
                lambda x, y, w, h: (x + _skew(w, h), y, w - 2 * _skew(w, h), h), pptx="FLOWCHART_DATA"),
    "document": _Spec(_document, lambda x, y, w, h: (x + w * 0.06, y, w * 0.88, h - 2 * _wave(h)),
                      pptx="FLOWCHART_DOCUMENT"),
    "predefined": _Spec(_predefined, lambda x, y, w, h: (x + min(0.1 * w, 18) + 4, y, w - 2 * min(0.1 * w, 18) - 8, h),
                        pptx="FLOWCHART_PREDEFINED_PROCESS"),
    "data": _Spec(_cylinder, lambda x, y, w, h: (x + w * 0.06, y + 2 * _cap(h), w * 0.88, h - 3 * _cap(h)),
                  pptx="CAN"),
    "connector": _Spec(lambda x, y, w, h: [Part(_circle_in(x, y, w, h))], _round_text, (40, 40), "OVAL"),
    "initial": _Spec(lambda x, y, w, h: [Part(_circle_in(x, y, w, h), "solid")], _round_text, (24, 24), "OVAL"),
    "final": _Spec(lambda x, y, w, h: [Part(_circle_in(x, y, w, h, 0.92), "stroke"),
                                       Part(_circle_in(x, y, w, h, 0.6), "solid")], _round_text, (32, 32), "group"),
    "flow_final": _Spec(_flow_final, _round_text, (28, 28), "FLOWCHART_SUMMING_JUNCTION"),
    "fork": _Spec(lambda x, y, w, h: [Part(_poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)]), "solid")],
                  lambda x, y, w, h: (x, y, w, h), (140, 8), "RECTANGLE"),
    "join": _Spec(lambda x, y, w, h: [Part(_poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)]), "solid")],
                  lambda x, y, w, h: (x, y, w, h), (140, 8), "RECTANGLE"),
    "merge": _Spec(_diamond, _inset(0.2, 0.2), (44, 44), "DIAMOND"),
    "choice": _Spec(_diamond, _inset(0.2, 0.2), (44, 44), "DIAMOND"),
    "history": _Spec(lambda x, y, w, h: [Part(_circle_in(x, y, w, h))], _round_text, (36, 36), "OVAL"),
    "deep_history": _Spec(lambda x, y, w, h: [Part(_circle_in(x, y, w, h))], _round_text, (36, 36), "OVAL"),
    "state": _Spec(lambda x, y, w, h: [Part(_rrect(x, y, w, h, 18))], _TEXT, pptx="ROUNDED_RECTANGLE"),
    "action": _Spec(lambda x, y, w, h: [Part(_rrect(x, y, w, h, 22))], _TEXT, pptx="ROUNDED_RECTANGLE"),
    "object": _Spec(_RECT, _TEXT, pptx="RECTANGLE"),
    "signal_send": _Spec(_send, lambda x, y, w, h: (x + w * 0.05, y, w * 0.95 - min(h / 2, w * 0.25), h),
                         pptx="PENTAGON"),
    "signal_receive": _Spec(_receive, lambda x, y, w, h: (x + min(h / 2, w * 0.25), y, w * 0.95 - min(h / 2, w * 0.25), h)),
}
KINDS = frozenset(GEOMETRY)
ROUND_KINDS = frozenset({"connector", "initial", "final", "flow_final", "history", "deep_history"})
DIAMOND_KINDS = frozenset({"decision", "merge", "choice"})
# extra width a text-sized symbol needs beyond a plain box so its text fits the text box
EXTRA_W = {"io": 0.5, "signal_send": 0.35, "signal_receive": 0.35, "terminator": 0.25, "predefined": 0.2,
           "decision": 0.0}
EXTRA_H = {"document": 0.3, "data": 0.45}


def parts(kind: str, x: float, y: float, w: float, h: float) -> list[Part]:
    return GEOMETRY[kind].parts(x, y, w, h)


def text_box(kind: str, x: float, y: float, w: float, h: float) -> Box:
    return GEOMETRY[kind].text(x, y, w, h)


def fixed_size(kind: str, vertical: bool = False) -> tuple[float, float] | None:
    size = GEOMETRY[kind].size if kind in GEOMETRY else None
    if size and vertical and kind in ("fork", "join"):
        return (size[1], size[0])
    return size


def pptx_plan(kind: str) -> str:
    return GEOMETRY[kind].pptx


def parse(d: str) -> list[Subpath]:
    """Absolute M/L/C/Z path → subpaths (the only commands this module writes)."""
    toks = d.replace(",", " ").split()
    subs: list[Subpath] = []
    i, cmd = 0, None
    while i < len(toks):
        t = toks[i]
        if t in ("M", "L", "C", "Z"):
            cmd = t
            i += 1
            if t == "Z":
                subs[-1].closed = True
            continue
        if cmd == "M":
            subs.append(Subpath((float(toks[i]), float(toks[i + 1]))))
            i += 2
            cmd = "L"
        elif cmd == "L":
            subs[-1].segments.append(("L", [(float(toks[i]), float(toks[i + 1]))]))
            i += 2
        elif cmd == "C":
            pts = [(float(toks[i + k]), float(toks[i + k + 1])) for k in (0, 2, 4)]
            subs[-1].segments.append(("C", pts))
            i += 6
        else:
            raise ValueError(f"unsupported path data near {t!r}")
    return subs
