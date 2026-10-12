"""Render examples/styling/gallery to cropped SVGs for the CSS docs (docs/public/assets/css/<id>.svg).

Run from the repo root: `uv run python docs/scripts/css_gallery.py`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from spinagram.api import scenes
from spinagram.backends.svg import to_svg
from spinagram.scene import Connector, Shape
from spinagram.yaml_io import load

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "public" / "assets" / "css"
PAD = 28


def bounds(sc) -> tuple[float, float, float, float]:
    """Box around the diagram content (nodes, zones, edge labels and edges), without title and chrome."""
    xs, ys = [], []
    for it in sc.items:
        if isinstance(it, Shape) and it.role in ("node", "zone", "pill"):
            xs += [it.x, it.x + it.w]
            ys += [it.y, it.y + it.h]
        elif isinstance(it, Connector):
            xs += [p[0] for p in it.points]
            ys += [p[1] for p in it.points]
            if it.label is not None:
                xs += [it.label.x, it.label.x + it.label.w]
                ys += [it.label.y, it.label.y + it.label.h]
    return min(xs) - PAD, min(ys) - PAD, max(xs) + PAD, max(ys) + PAD


def crop(svg: str, box: tuple[float, float, float, float]) -> str:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    return re.sub(r'viewBox="[^"]+" width="[^"]+" height="[^"]+"',
                  f'viewBox="{x0:.0f} {y0:.0f} {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}"', svg, count=1)


_SGR = {"1": {"fontWeight": 600}, "2": {"opacity": 0.6}, "9": {"textDecoration": "line-through"},
        "31": {"color": "#FCA5A5"}, "33": {"color": "#FCD34D"}, "35": {"color": "#F0ABFC"}, "36": {"color": "#67E8F9"}}
TERMINAL = {"background": "#0B1120", "color": "#E2E8F0", "border": "1px solid #1E293B", "borderRadius": 12,
            "padding": "16px 18px", "overflowX": "auto", "fontSize": 12.5, "lineHeight": 1.55,
            "fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace", "margin": "16px 0"}


def ansi_to_jsx(text: str) -> str:
    """ANSI SGR output (bold, dim, strike, colours, 24-bit backgrounds) as an MDX ``<pre>`` of styled spans."""
    out, style = [], {}
    for part in re.split(r"(\x1b\[[\d;]*m)", text):
        m = re.fullmatch(r"\x1b\[([\d;]*)m", part)
        if m:
            codes = m.group(1).split(";")
            if codes == ["0"] or codes == [""]:
                style = {}
            elif codes[:2] == ["48", "2"]:
                style = {**style, "background": "#%02X%02X%02X" % tuple(map(int, codes[2:5])), "borderRadius": 2}
            else:
                for c in codes:
                    style = {**style, **_SGR.get(c, {})}
            continue
        if not part:
            continue
        lit = "{" + json.dumps(part, ensure_ascii=False) + "}"
        out.append(f"<span style={{{json.dumps(style)}}}>{lit}</span>" if style else lit)
    return f'<pre className="not-prose" style={{{json.dumps(TERMINAL)}}}>' + "".join(out) + "</pre>"


def inspect_output() -> None:
    """Run `check --styles` on the styled example and paste its coloured output into the docs page."""
    env = {**os.environ, "COLUMNS": "200"}
    env.pop("NO_COLOR", None)
    cmd = [sys.executable, "-m", "spinagram.cli", "check", "--styles", "--color", "always",
           "examples/styling/styled.py", "--select", "#payments"]
    text = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True).stdout.rstrip("\n")
    page = ROOT / "docs" / "content" / "docs" / "css-reference.mdx"
    src = page.read_text(encoding="utf-8")
    start = src.index("{/* inspect-output:start")
    start = src.index("\n", start) + 1
    end = src.index("{/* inspect-output:end */}")
    page.write_text(src[:start] + ansi_to_jsx(text) + "\n" + src[end:], encoding="utf-8")
    print(page.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for sc in scenes(load(ROOT / "examples" / "styling" / "gallery" / "gallery.py")):
        path = OUT / f"{sc.id.lower()}.svg"
        path.write_text(crop(to_svg(sc), bounds(sc)), encoding="utf-8")
        print(path.relative_to(ROOT))
    inspect_output()


if __name__ == "__main__":
    main()
