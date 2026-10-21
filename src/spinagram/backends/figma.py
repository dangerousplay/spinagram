"""Figma: Plugin-API JavaScript for the Figma MCP ``use_figma`` tool.

Each diagram becomes a frame (Design files), a slide (Slides files) or a section (FigJam
boards) named ``spinagram:<id>``. Running the script again clears that container and
rebuilds it in place, so its position on the canvas survives re-renders.

Native, editable nodes: rectangles, vector diamonds, text with the theme fonts, tables as
grouped cells. Edges:

* FigJam: an edge whose both ends sit on box sides becomes a native **connector** attached
  to the two boxes (moving a box drags the line; elbowed/straight/curved, label as connector
  text). Free-floating edges stay vectors.
* Design / Slides: vectors with arrow caps (the connector node is FigJam-only).

Icons: SVG icons are inlined and rebuilt with ``figma.createNodeFromSvg`` (editable vectors,
no upload). Raster images cannot be created inside ``use_figma`` (only ``upload_assets`` may
add image bytes): the script draws a placeholder rectangle and returns
``imageTargets: [{nodeId, asset}]``; ``<slug>.assets.json`` maps each asset key to its local
file. The follow-up is ``upload_assets(fileKey, count=n, nodeIds=[...])`` and POSTing each
file to its returned URL.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .. import shapes
from ..scene import Connector, Image, Label, Line, Scene, Shape, TableGrid, Text, TextBlock

CHUNK_LIMIT = 45_000

PRELUDE = r"""
const NAME = %(name)s, W = %(w)s, H = %(h)s, BG = %(bg)s, FIRST = %(first)s;
const isSlides = figma.editorType === 'slides', isJam = figma.editorType === 'figjam';
const rgb = (h) => ({ r: parseInt(h.slice(1,3),16)/255, g: parseInt(h.slice(3,5),16)/255, b: parseInt(h.slice(5,7),16)/255 });
const solid = (h, o) => (o === undefined || o >= 1) ? [{ type: 'SOLID', color: rgb(h) }] : [{ type: 'SOLID', color: rgb(h), opacity: o }];
function deco(n, o) {  // CSS dash patterns, drop shadows and line opacity
  if (o.dashes) n.dashPattern = o.dashes;
  if (o.lineOpacity !== undefined) n.opacity = o.lineOpacity;
  if (o.shadow) { const s = o.shadow;
    n.effects = [{ type: 'DROP_SHADOW', color: Object.assign(rgb(s.color), { a: s.a }), offset: { x: s.x, y: s.y },
                   radius: s.blur, spread: 0, visible: true, blendMode: 'NORMAL' }]; }
}
const fonts = {};
async function font(family, style) {
  const key = family + '|' + style;
  if (fonts[key]) return fonts[key];
  try { await figma.loadFontAsync({ family, style }); fonts[key] = { family, style }; }
  catch (e) { const fb = { family: 'Inter', style: /Bold/.test(style) ? 'Bold' : 'Regular' };
              await figma.loadFontAsync(fb); fonts[key] = fb; }
  return fonts[key];
}
let root = figma.currentPage.findOne(n => n.name === NAME);
if (!root) {
  if (!FIRST) throw new Error('run chunk 1 first: container ' + NAME + ' not found');
  root = isSlides ? figma.createSlide() : isJam ? figma.createSection() : figma.createFrame();
  root.name = NAME;
  if (!isSlides) {
    const xs = figma.currentPage.children.filter(n => n !== root).map(n => n.x + n.width);
    root.x = xs.length ? Math.max(...xs) + 200 : 0; root.y = 0;
    if (isJam) root.resizeWithoutConstraints(W, H); else { root.resize(W, H); root.clipsContent = true; }
  }
} else if (FIRST) {
  for (const c of [...root.children]) c.remove();
}
root.fills = solid(BG);
const created = [], imageTargets = [];
function put(node, name) { node.name = name; root.appendChild(node); created.push(node.id); return node; }
function rect(name, x, y, w, h, o) {
  const r = figma.createRectangle(); r.resize(Math.max(w, 0.01), Math.max(h, 0.01)); r.x = x; r.y = y;
  r.fills = o.fill ? solid(o.fill, (o.opacity ?? 1) * (o.fillOpacity ?? 1)) : [];
  if (o.stroke && o.sw) { r.strokes = solid(o.stroke); r.strokeWeight = o.sw; r.strokeAlign = 'CENTER';
                          if (o.dash) r.dashPattern = [10, 7]; }
  if (o.radius) r.cornerRadius = o.radius;
  deco(r, o);
  return put(r, name);
}
async function vec(name, x0, y0, net, o) {
  const v = figma.createVector();
  if (v.setVectorNetworkAsync) await v.setVectorNetworkAsync(net); else v.vectorNetwork = net;
  v.x = x0; v.y = y0;
  v.fills = o.fill ? solid(o.fill, (o.opacity ?? 1) * (o.fillOpacity ?? 1)) : [];
  v.strokes = o.stroke ? solid(o.stroke) : []; v.strokeWeight = o.sw || 1; v.strokeJoin = 'ROUND';
  if (o.dash) v.dashPattern = [10, 7];
  deco(v, o);
  return put(v, name);
}
async function text(name, s, x, y, o) {
  const t = figma.createText();
  t.fontName = await font(o.family, o.style);
  t.fontSize = o.size; t.characters = s; t.fills = solid(o.color);
  t.lineHeight = { unit: 'PIXELS', value: o.leading };
  if (o.ls) t.letterSpacing = { unit: 'PIXELS', value: o.ls };
  t.textAlignHorizontal = o.align || 'LEFT';
  if (o.w) { t.textAutoResize = 'HEIGHT'; t.resize(o.w, t.height); } else { t.textAutoResize = 'WIDTH_AND_HEIGHT'; }
  t.x = o.anchor === 'middle' ? x - t.width / 2 : o.anchor === 'end' ? x - t.width : x; t.y = y;
  return put(t, name);
}
function image(name, asset, x, y, w, h) {
  const r = rect(name, x, y, w, h, { fill: '#EEEEEE' });
  r.name = name + ' · asset:' + asset;  // image_fill_js fills every copy by hash (no pluginData in use_figma)
  imageTargets.push({ nodeId: r.id, asset }); return r;
}
const LIB = {};
function libIcon(key) {
  if (!(key in LIB)) LIB[key] = figma.currentPage.findOne(n => n.name === 'dk-icon:' + key) || null;
  return LIB[key];
}
// icon from the board's icon library (exact uploaded bytes), else inline SVG, else placeholder
function icon(name, key, x, y, w, h) {
  const src = libIcon(key);
  if (src) { const n = src.clone(); n.resize(w, h); n.x = x; n.y = y; return put(n, name); }
  return SVG[key] ? svgIcon(name, key, x, y, w) : image(name, key, x, y, w, h);
}
function svgIcon(name, key, x, y, size) {
  let n = null;
  try { n = figma.createNodeFromSvg(SVG[key]); } catch (e) { n = null; }
  if (!n) return image(name, key, x, y, size, size);
  n.resize(size, size); n.x = x; n.y = y;
  return put(n, name);
}
function find(id) {
  return root.findOne(n => n.name === id && n.type !== 'TEXT' && n.type !== 'GROUP' && n.type !== 'CONNECTOR');
}
// side centres → magnets; other points → position in px from the node's top-left (FigJam reads px, not 0–1)
function endpoint(node, p) {
  const m = p.x === 0.5 && p.y === 0 ? 'TOP' : p.x === 0.5 && p.y === 1 ? 'BOTTOM'
          : p.x === 0 && p.y === 0.5 ? 'LEFT' : p.x === 1 && p.y === 0.5 ? 'RIGHT' : null;
  return m ? { endpointNodeId: node.id, magnet: m }
           : { endpointNodeId: node.id, position: { x: p.x * node.width, y: p.y * node.height } };
}
// FigJam: native connector attached to both boxes; returns null (caller draws a vector) elsewhere
async function link(name, a, pa, b, pb, o) {
  if (!isJam || !figma.createConnector) return null;
  const A = find(a), B = find(b);
  if (!A || !B) return null;
  const c = figma.createConnector();
  c.connectorStart = endpoint(A, pa);
  c.connectorEnd = endpoint(B, pb);
  c.connectorLineType = o.line;
  c.connectorStartStrokeCap = o.capStart ? (o.capStartType || 'ARROW_EQUILATERAL') : 'NONE';
  c.connectorEndStrokeCap = o.capEnd ? (o.capEndType || 'ARROW_EQUILATERAL') : 'NONE';
  c.strokes = solid(o.stroke); c.strokeWeight = o.sw;
  if (o.dash) c.dashPattern = o.dashes || [10, 7];
  if (o.label) {
    c.text.fontName = await font(o.label.family, o.label.style);
    c.text.characters = o.label.text; c.text.fontSize = o.label.size;
  }
  return put(c, name);
}
function group(nodes, name) { if (nodes.length < 2) return nodes[0]; const g = figma.group(nodes, root); g.name = name; return g; }
"""

EPILOGUE = "\nreturn { container: root.id, name: NAME, created: created.length, imageTargets };\n"


def _j(v) -> str:
    return json.dumps(_int(v), ensure_ascii=False, separators=(",", ":"))


def _int(v):
    """240.0 → 240 so the emitted JS stays short."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, dict):
        return {k: _int(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_int(x) for x in v]
    return v


def _r(v: float):
    v = round(float(v), 2)
    return int(v) if v.is_integer() else v


def _compact(o: dict) -> dict:
    """Drop keys the JS helpers treat as defaults (None/False/0) — keeps scripts under the 50 KB use_figma cap."""
    return {k: (_r(v) if isinstance(v, float) else v) for k, v in o.items() if v not in (None, False, 0, 0.0)}


def _net(d: str, ox: float, oy: float, fill: bool) -> dict:
    """Symbol path → Figma vector network relative to (ox, oy); closed subpaths become fill regions."""
    verts: list[dict] = []
    segs: list[dict] = []
    loops: list[list[int]] = []

    def vert(p) -> int:
        verts.append({"x": _r(p[0] - ox), "y": _r(p[1] - oy)})
        return len(verts) - 1

    for sub in shapes.parse(d):
        first = cur = vert(sub.start)
        cur_pt = sub.start
        loop: list[int] = []
        for n, (cmd, pts) in enumerate(sub.segments):
            end = pts[-1]
            last = n == len(sub.segments) - 1
            ei = first if sub.closed and last and abs(end[0] - sub.start[0]) < 1e-6 and abs(end[1] - sub.start[1]) < 1e-6 \
                else vert(end)
            seg = {"start": cur, "end": ei}
            if cmd == "C":
                (c1, c2) = pts[0], pts[1]
                seg["tangentStart"] = {"x": _r(c1[0] - cur_pt[0]), "y": _r(c1[1] - cur_pt[1])}
                seg["tangentEnd"] = {"x": _r(c2[0] - end[0]), "y": _r(c2[1] - end[1])}
            segs.append(seg)
            loop.append(len(segs) - 1)
            cur, cur_pt = ei, end
        if sub.closed:
            if cur != first:
                segs.append({"start": cur, "end": first})
                loop.append(len(segs) - 1)
            loops.append(loop)
    net: dict = {"vertices": verts, "segments": segs}
    if fill and loops:
        net["regions"] = [{"windingRule": "NONZERO", "loops": loops}]
    return net


_CAP = {"arrow": "ARROW_EQUILATERAL", "open-arrow": "ARROW_LINES", "diamond": "DIAMOND_FILLED",
        "open-diamond": "DIAMOND_FILLED", "circle": "CIRCLE_FILLED", "bar": "NONE"}


_WARNED: set[tuple[str, str]] = set()


def _cap(kind: str, prop: str) -> str:
    if kind in ("open-diamond", "bar") and (prop, kind) not in _WARNED:  # once per property and value
        import warnings

        _WARNED.add((prop, kind))
        warnings.warn(f"figma: {prop} '{kind}' has no Figma stroke cap; drawn as {_CAP[kind].lower()}", stacklevel=3)
    return _CAP.get(kind, "ARROW_EQUILATERAL")


def _style(s) -> dict:
    """CSS extras for rect()/vec(): dash pattern and drop shadow."""
    out: dict = {}
    if getattr(s, "dash", None):
        out["dashes"] = [_r(v) for v in s.dash]
    if isinstance(s, Connector) and s.opacity < 1:
        out["lineOpacity"] = round(s.opacity, 3)
    if getattr(s, "fill_opacity", 1.0) < 1:
        out["fillOpacity"] = round(s.fill_opacity, 3)
    sh = getattr(s, "shadow", None)
    if sh:
        out["shadow"] = {"x": _r(sh[0]), "y": _r(sh[1]), "blur": _r(sh[2]), "color": sh[3], "a": round(sh[4], 3)}
    return out


def _pos(b) -> dict:
    """Binding (side, frac) → FigJam endpoint position relative to the box (0–1)."""
    f = _r(b.frac)
    return {"top": {"x": f, "y": 0}, "bottom": {"x": f, "y": 1}, "left": {"x": 0, "y": f},
            "right": {"x": 1, "y": f}}.get(b.side, {"x": 0.5, "y": 0.5})


class _Emitter:
    def __init__(self, scene: Scene, library: bool = False):
        self.s = scene
        self.library = library  # icons come from `dk-icon:<file>` nodes on the page (see icon_library_js)
        self.parts: list[str] = []
        self.assets: dict[str, str] = {}
        self.svgs: dict[str, str] = {}

    def asset(self, path: Path) -> str:
        key = path.name
        self.assets.setdefault(key, str(path))
        return key

    def svg(self, path: Path) -> str:
        key = path.name
        if key not in self.svgs:
            self.svgs[key] = path.read_text(encoding="utf-8")
            self.assets.setdefault(key, str(path))  # placeholder fallback if the editor rejects the SVG
        return key

    # code builders ------------------------------------------------------------
    def _txt(self, var: str, name: str, s: str, x: float, y: float, b: TextBlock, *, w: float | None = None,
             align: str = "LEFT", anchor: str = "start", ls: float = 0) -> str:
        o = {"family": b.font.family, "style": b.font.figma_style, "size": b.font.size, "color": b.color,
             "leading": _r(b.leading)}
        if align != "LEFT":
            o["align"] = align
        if anchor != "start":
            o["anchor"] = anchor
        if w:
            o["w"] = _r(w + 2)
        if ls:
            o["ls"] = ls
        return f"const {var} = await text({_j(name)}, {_j(s)}, {_r(x)}, {_r(y)}, {_j(o)});"

    def label(self, base: str, label: Label, prewrapped: bool) -> tuple[list[str], list[str]]:
        code, names = [], []
        align = "CENTER" if label.align == "center" else "LEFT"
        for i, (b, x, top) in enumerate(label.place()):
            var = f"{base}_t{i}"
            s = "\n".join(b.lines if prewrapped else b.paragraphs)
            bx, _, bw, _ = label.box
            code.append(self._txt(var, f"{base} text {i}", s, bx, top, b, w=bw, align=align))
            names.append(var)
        return code, names

    def shape(self, s: Shape, v: str | None = None) -> str:
        v = v or f"n_{len(self.parts)}"
        o = _compact({"fill": s.fill, "stroke": s.stroke, "sw": s.stroke_width, "dash": s.dashed, "radius": s.radius,
                      "opacity": s.opacity if s.opacity < 1 else None}) | _style(s)
        if s.parts:
            code = []
            members_v = []
            for i, part in enumerate(s.parts):
                pv = v if i == 0 else f"{v}_p{i}"
                po = _compact({"fill": None if part.paint == "stroke" else (s.stroke if part.paint == "solid" else s.fill),
                               "stroke": s.stroke, "sw": s.stroke_width, "dash": s.dashed,
                               "opacity": s.opacity if s.opacity < 1 else None}) | (_style(s) if i == 0 else {})
                net = _net(part.d, s.x, s.y, fill=part.paint != "stroke")
                code.append(f"const {pv} = await vec({_j(s.id)}, {_r(s.x)}, {_r(s.y)}, {_j(net)}, {_j(po)});")
                members_v.append(pv)
            members = list(members_v)
            if s.label:
                lc, ln = self.label(v, s.label, prewrapped=False)
                code += lc
                members += ln
            if len(members) > 1:
                code.append(f"group([{', '.join(members)}], {_j(s.id + ' (group)')});")
            return "\n".join(code)
        if s.kind == "diamond":
            w, h = s.w, s.h
            net = {"vertices": [{"x": w / 2, "y": 0}, {"x": w, "y": h / 2}, {"x": w / 2, "y": h}, {"x": 0, "y": h / 2}],
                   "segments": [{"start": i, "end": (i + 1) % 4} for i in range(4)],
                   "regions": [{"windingRule": "NONZERO", "loops": [[0, 1, 2, 3]]}]}
            code = [f"const {v} = await vec({_j(s.id)}, {_r(s.x)}, {_r(s.y)}, {_j(net)}, {_j(o)});"]
        else:
            code = [f"const {v} = rect({_j(s.id)}, {_r(s.x)}, {_r(s.y)}, {_r(s.w)}, {_r(s.h)}, {_j(o)});"]
        members = [v]
        if s.icon:
            iv = f"{v}_icon"
            if self.library:
                code.append(f"const {iv} = icon({_j(s.id + ' icon')}, {_j(self.asset(s.icon.path))}, {_r(s.icon.x)}, "
                            f"{_r(s.icon.y)}, {_r(s.icon.width)}, {_r(s.icon.size)});")
            elif s.icon.path.suffix.lower() == ".svg":
                code.append(f"const {iv} = svgIcon({_j(s.id + ' icon')}, {_j(self.svg(s.icon.path))}, {_r(s.icon.x)}, "
                            f"{_r(s.icon.y)}, {_r(s.icon.size)});")
            else:
                code.append(f"const {iv} = image({_j(s.id + ' icon')}, {_j(self.asset(s.icon.path))}, {_r(s.icon.x)}, "
                            f"{_r(s.icon.y)}, {_r(s.icon.width)}, {_r(s.icon.size)});")
            members.append(iv)
        if s.label:
            lc, ln = self.label(v, s.label, prewrapped=s.kind in ("diamond", "pill"))
            code += lc
            members += ln
        if len(members) > 1:
            code.append(f"group([{', '.join(members)}], {_j(s.id + ' (group)')});")
        return "\n".join(code)

    def connector(self, c: Connector) -> str:
        pts = c.points
        if c.route == "curve":
            (x0, y0), (qx, qy), (x2, y2) = pts
            verts = [(x0, y0), (x2, y2)]
            seg = [{"start": 0, "end": 1, "tangentStart": {"x": 2 / 3 * (qx - x0), "y": 2 / 3 * (qy - y0)},
                    "tangentEnd": {"x": 2 / 3 * (qx - x2), "y": 2 / 3 * (qy - y2)}}]
        else:
            verts = list(pts)
            seg = [{"start": i, "end": i + 1} for i in range(len(verts) - 1)]
        mx = min(x for x, _ in pts)
        my = min(y for _, y in pts)
        vs = [{"x": _r(x - mx), "y": _r(y - my)} for x, y in verts]
        if c.arrow_end:
            vs[-1]["strokeCap"] = _cap(c.marker_end, "marker-end")
        if c.arrow_start:
            vs[0]["strokeCap"] = _cap(c.marker_start, "marker-start")
        net = {"vertices": vs, "segments": seg}
        v = f"n_{len(self.parts)}"
        fallback = [f"await vec({_j(c.id)}, {_r(mx)}, {_r(my)}, {_j(net)}, "
                    f"{_j(_compact({'stroke': c.color, 'sw': c.width, 'dash': c.dashed}) | _style(c))});"]
        if c.label:
            fallback.append(self.shape(c.label, f"{v}_lab"))
        if not (c.src and c.dst):
            return "\n".join(fallback)
        o = _compact({"line": {"straight": "STRAIGHT", "curve": "CURVED"}.get(c.route, "ELBOWED"), "stroke": c.color,
                      "sw": c.width, "dash": c.dashed, "capStart": c.arrow_start, "capEnd": c.arrow_end}) | _style(c)
        if c.marker_start != "arrow" and c.arrow_start:
            o["capStartType"] = vs[0]["strokeCap"]
        if c.marker_end != "arrow" and c.arrow_end:
            o["capEndType"] = vs[-1]["strokeCap"]
        lab = c.label.label.blocks[0] if c.label and c.label.label and c.label.label.blocks else None
        if lab:
            o["label"] = {"text": " ".join(lab.paragraphs), "family": lab.font.family, "style": lab.font.figma_style,
                          "size": lab.font.size}
        return (f"if (!(await link({_j(c.id)}, {_j(c.src.shape_id)}, {_j(_pos(c.src))}, {_j(c.dst.shape_id)}, "
                f"{_j(_pos(c.dst))}, {_j(o)}))) {{\n" + "\n".join(fallback) + "\n}")

    def text(self, t: Text) -> str:
        v = f"n_{len(self.parts)}"
        align = {"middle": "CENTER", "end": "RIGHT"}.get(t.anchor, "LEFT")
        return self._txt(v, t.id, "\n".join(t.block.lines), t.x, t.top, t.block, align=align, anchor=t.anchor,
                         ls=t.letter_spacing)

    def line(self, ln: Line) -> str:
        net = {"vertices": [{"x": 0, "y": 0}, {"x": _r(ln.x2 - ln.x1), "y": _r(ln.y2 - ln.y1)}],
               "segments": [{"start": 0, "end": 1}]}
        return (f"await vec({_j(ln.id)}, {_r(min(ln.x1, ln.x2))}, {_r(min(ln.y1, ln.y2))}, {_j(net)}, "
                f"{_j({'stroke': ln.color, 'sw': ln.width})});")

    def image(self, im: Image) -> str:
        return f"image({_j(im.id)}, {_j(self.asset(im.path))}, {_r(im.x)}, {_r(im.y)}, {_r(im.w)}, {_r(im.h)});"

    def table(self, t: TableGrid) -> str:
        code, members = [], []
        y = t.y
        base = f"n_{len(self.parts)}"
        for r, (rh, row) in enumerate(zip(t.row_heights, t.cells)):
            x = t.x
            for c, (cw, cell) in enumerate(zip(t.col_widths, row)):
                v = f"{base}_{r}_{c}"
                code.append(f"const {v} = rect({_j(f'{t.id}[{r},{c}]')}, {_r(x)}, {_r(y)}, {_r(cw)}, {_r(rh)}, "
                            f"{_j({'fill': cell.fill})});")
                members.append(v)
                if cell.icon:
                    code.append(f"const {v}_i = image({_j(f'{t.id}[{r},{c}] icon')}, {_j(self.asset(cell.icon.path))}, "
                                f"{_r(x + 14)}, {_r(y + (rh - cell.icon.size) / 2)}, {_r(cell.icon.size)}, "
                                f"{_r(cell.icon.size)});")
                    members.append(f"{v}_i")
                b = cell.block
                top = y + (rh - b.height) / 2
                code.append(self._txt(f"{v}_t", f"{t.id}[{r},{c}] text", "\n".join(b.paragraphs), x + cell.pad_left,
                                      top, b, w=cw - cell.pad_left - 10))
                members.append(f"{v}_t")
                x += cw
            if r > 0:
                code.append(f"const {base}_b{r} = rect({_j(f'{t.id} rule {r}')}, {_r(t.x)}, {_r(y + rh - 1)}, "
                            f"{_r(t.w)}, 1, {_j({'fill': t.border})});")
                members.append(f"{base}_b{r}")
            y += rh
        code.append(f"group([{', '.join(members)}], {_j(t.id)});")
        return "\n".join(code)

    def build(self) -> list[str]:
        for it in self.s.items:
            if isinstance(it, Shape):
                self.parts.append(self.shape(it))
            elif isinstance(it, Connector):
                self.parts.append(self.connector(it))
            elif isinstance(it, Text):
                self.parts.append(self.text(it))
            elif isinstance(it, Line):
                self.parts.append(self.line(it))
            elif isinstance(it, Image):
                self.parts.append(self.image(it))
            elif isinstance(it, TableGrid):
                self.parts.append(self.table(it))
        return self.parts


def to_figma_js(scene: Scene, limit: int = CHUNK_LIMIT, library: bool = False) -> tuple[list[str], dict[str, str]]:
    """Return (scripts in run order, asset key → local path).

    ``library=True``: icons are cloned from ``dk-icon:<file>`` nodes already on the page instead of
    being inlined — run :func:`icon_library_js` once after uploading the files with ``upload_assets``.
    Scripts shrink a lot and SVG bytes are exactly the uploaded files.
    """
    em = _Emitter(scene, library)
    parts = em.build()
    name = f"spinagram:{scene.id}"
    chunks: list[list[str]] = [[]]
    size = 0
    budget = limit - len(PRELUDE) - 400 - sum(len(v) for v in em.svgs.values())
    for p in parts:
        if chunks[-1] and size + len(p) > budget:
            chunks.append([])
            size = 0
        chunks[-1].append(p)
        size += len(p) + 1
    scripts = []
    for i, body in enumerate(chunks):
        head = PRELUDE % {"name": _j(name), "w": _r(scene.width), "h": _r(scene.height), "bg": _j(scene.background),
                          "first": "true" if i == 0 else "false"}
        code = "\n".join(body)
        svg = {k: v for k, v in em.svgs.items() if "svgIcon(" in code and _j(k) in code}
        scripts.append(f"// spinagram {scene.id} chunk {i + 1}/{len(chunks)}\n" + head
                       + f"const SVG = {_j(svg)};\n" + code + EPILOGUE)
    return scripts, em.assets


def icon_library_js(uploads: dict[str, str], *, x: float = 0, y: float = -1200) -> str:
    """Script that turns uploaded icon layers into the board's icon library.

    ``uploads`` maps each asset file name (``ec2.svg``, ``safe-green.png``) to the node id
    ``upload_assets`` returned for it — or to ``None``: the layer is then found by name (a multipart
    upload names the layer after the file). The nodes are renamed ``dk-icon:<file>`` and laid out in
    a section ``spinagram:icons``; diagram scripts built with ``library=True`` clone them.
    """
    return (f"const U = {_j(uploads)}; const X = {_r(x)}, Y = {_r(y)};\n"
            "const byName = (k) => figma.currentPage.findOne(n => n.parent === figma.currentPage && "
            "(n.name === k || n.name === k.replace(/\\.[^.]+$/, '')));\n"
            "let sec = figma.currentPage.findOne(n => n.name === 'spinagram:icons');\n"
            "if (!sec) { sec = figma.createSection(); sec.name = 'spinagram:icons'; sec.x = X; sec.y = Y; }\n"
            "const keys = Object.keys(U).sort(); const done = [], missing = [];\n"
            "for (const [i, k] of keys.entries()) {\n"
            "  const n = U[k] ? await figma.getNodeByIdAsync(U[k]) : byName(k); if (!n) { missing.push(k); continue; }\n"
            "  n.name = 'dk-icon:' + k; const s = 64 / Math.max(n.width, n.height); n.resize(n.width * s, n.height * s);\n"
            "  sec.appendChild(n); n.x = 40 + (i % 10) * 96; n.y = 60 + Math.floor(i / 10) * 96; done.push(n.id);\n"
            "}\n"
            "sec.resizeWithoutConstraints(40 + 10 * 96, 60 + Math.ceil(keys.length / 10) * 96 + 20);\n"
            "return { section: sec.id, mutatedNodeIds: done, missing };\n")


def image_fill_js(hashes: dict[str, str]) -> str:
    """Script that fills every image placeholder with an already-uploaded image, by asset key.

    Upload each distinct file once (``upload_assets`` without ``nodeIds`` returns its
    ``imageHash``), then run this once: an icon used 30 times costs one upload. Remove the
    layers ``upload_assets`` dropped on the canvas afterwards (their ids are in its response).
    """
    return (f"const H = {_j(hashes)}; const filled = [];\n"
            "for (const n of figma.currentPage.findAll(n => / · asset:[^ ]+$/.test(n.name) && 'fills' in n)) {\n"
            "  const h = H[n.name.split(' · asset:').pop()];\n"
            "  if (h) { n.fills = [{ type: 'IMAGE', imageHash: h, scaleMode: 'FIT' }]; filled.push(n.id); }\n"
            "}\nreturn { filled: filled.length, mutatedNodeIds: filled };\n")


class FigmaBackend:
    name = "figma"

    def __init__(self, limit: int = CHUNK_LIMIT, library: bool = False):
        self.limit = limit
        self.library = library

    def render(self, scenes: Sequence[Scene], out_dir: Path) -> list[Path]:
        d = out_dir / "figma"
        d.mkdir(parents=True, exist_ok=True)
        paths = []
        for sc in scenes:
            scripts, assets = to_figma_js(sc, self.limit, self.library)
            for i, js in enumerate(scripts, 1):
                p = d / f"{sc.slug}-{i:02d}.js"
                p.write_text(js, encoding="utf-8")
                paths.append(p)
            m = d / f"{sc.slug}.assets.json"
            m.write_text(json.dumps({"container": f"spinagram:{sc.id}", "assets": assets}, indent=2,
                                    ensure_ascii=False), encoding="utf-8")
            paths.append(m)
        return paths


FIGJAM_README = """# FigJam hand-off (spinagram)

1. Load the Figma skills `figma-use` and `figma-use-figjam`.
2. Icons (once per board): `upload_assets(fileKey, count={n})`, then POST every file in `icons/`
   as multipart (`-F "file=@icons/<name>"`) — the layer is named after the file.
3. Run `icon-library.js` with `use_figma`: the uploaded layers become `dk-icon:<file>` in a
   `spinagram:icons` section. Keep that section: diagrams clone their icons from it.
4. Run each `<slug>-NN.js` with `use_figma`, in order. Each diagram becomes a section
   `spinagram:<id>`; edges between boxes are native connectors. Re-running rebuilds in place.

Icons: {icons}
"""


class FigjamBackend(FigmaBackend):
    """FigJam board: library-mode scripts + the icon bundle and the library script that registers it."""

    name = "figjam"

    def __init__(self, limit: int = CHUNK_LIMIT):
        super().__init__(limit, library=True)

    def render(self, scenes: Sequence[Scene], out_dir: Path) -> list[Path]:
        import shutil

        paths = super().render(scenes, out_dir)
        d = out_dir / "figma"
        icons_dir = d / "icons"
        icons_dir.mkdir(exist_ok=True)
        assets: dict[str, str] = {}
        for sc in scenes:
            assets.update(to_figma_js(sc, self.limit, True)[1])
        for key, src in sorted(assets.items()):
            shutil.copyfile(src, icons_dir / key)
            paths.append(icons_dir / key)
        manifest = d / "icons.json"
        manifest.write_text(json.dumps({k: f"icons/{k}" for k in sorted(assets)}, indent=1), encoding="utf-8")
        lib = d / "icon-library.js"
        lib.write_text(icon_library_js({k: None for k in sorted(assets)}), encoding="utf-8")
        readme = d / "README.md"
        readme.write_text(FIGJAM_README.format(n=len(assets), icons=", ".join(sorted(assets)) or "none"), encoding="utf-8")
        return paths + [manifest, lib, readme]
