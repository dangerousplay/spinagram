"""Load diagrams from YAML files and Python modules."""
from __future__ import annotations

import runpy
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import yaml

from .model import NOTE_VARIANTS, Diagram, Edge, Group, Legend, Table, Zone, normalize_tags, parse_edge

_NODE_KEYS = {"id", "kind", "x", "y", "w", "h", "title", "text", "lines", "style", "icon", "icon_size", "align",
              "title_size", "body_size", "radius", "dashed", "color", "in", "class", "css", "cell"}
_NODE_EXTRA = {"weight", "font", "variant",  # kind: text options; kind: note variant
               "fit", "min_scale", "break_on",  # text fitting
               "badges",  # corner badge icons
               "size", "role", "max_width"}  # free labels
_SNAKE_KEYS = {"steps", "cols", "y", "h", "x", "w", "gap", "row_gap", "zones", "mode", "chain"}
_CONTAINER_KEYS = {"x", "y", "gap", "same_size", "max_width", "same_icon_size", "zone", "align", "cols",
                   "same_text_scale"}
_GROUP_KEYS = {"id", "label", "style", "icon", "children", "direction", "columns", "gap", "padding", "align",
               "class", "css"}


def _groups(d: Diagram, items: list, parent: Group | None) -> None:
    """Flatten the ``groups:`` tree; a child is a node id (string) or a nested group mapping."""
    for g in items or []:
        if isinstance(g, str):
            if parent is None:
                raise ValueError(f"{d.id}: top-level groups entry {g!r} must be a mapping")
            parent.children.append(g)
            continue
        g = dict(g)
        unknown = set(g) - _GROUP_KEYS
        if unknown:
            raise ValueError(f"{d.id}: group {g.get('id', g.get('label'))!r} has unknown keys {sorted(unknown)}")
        kids = g.pop("children", None) or []
        if "id" not in g:
            g["id"] = "g-" + ("".join(c if c.isalnum() else "-" for c in str(g.get("label") or len(d.groups) + 1).lower())
                              .strip("-")[:24])
        if any(o.id == g["id"] for o in d.groups):
            raise ValueError(f"{d.id}: duplicate group id {g['id']!r}")
        if "class" in g:
            g["cls"] = g.pop("class")
        grp = Group(**g)
        d.groups.append(grp)
        if parent is not None:
            parent.children.append(grp.id)
        _groups(d, kids, grp)


def _node(d: Diagram, n: dict, data: dict[str, Any]) -> None:
    n = dict(n)
    if "at" in n:  # shorthand: at: [x, y, w, h]
        n["x"], n["y"], *wh = n.pop("at")
        if wh:
            n["w"], n["h"] = wh
    if isinstance(n.get("id"), bool):
        raise ValueError(f"{data['id']}: node id {n['id']!r} is a YAML boolean — "
                         "yes/no/on/off must be quoted (id: \"no\") or renamed")
    kind = n.pop("kind", "box")
    title = n.pop("title", None)
    unknown = [k for k in n if k not in _NODE_KEYS | _NODE_EXTRA and not str(k).startswith("x-")]
    if unknown:
        raise ValueError(f"{data['id']}: node {n.get('id', title)!r} has unknown keys {unknown} "
                         "(unquoted commas in a flow mapping split the value — quote it)")
    parent = n.pop("in", None)
    if "class" in n:
        n["cls"] = n.pop("class")
    extra = {k: n.pop(k) for k in list(n) if k not in _NODE_KEYS | {"cls"}}
    node = d.add(kind, title, **n, **extra)  # extras land in node.extra (and are validated there)
    if parent is not None:
        g = next((g for g in d.groups if g.id == parent), None)
        if g is None:
            raise ValueError(f"{data['id']}: node {node.id!r} is `in` unknown group {parent!r}")
        g.children.append(node.id)


def from_dict(data: dict[str, Any], base_dir: Path | None = None) -> Diagram:
    for req in ("id", "title"):
        if req not in data:
            raise ValueError(f"diagram is missing required key {req!r}")
    d = Diagram(id=str(data["id"]), title=str(data["title"]), subtitle=data.get("subtitle"),
                source=data.get("source"), kicker=data.get("kicker"), base_dir=base_dir,
                facts=data.get("facts"), locale=data.get("locale"),
                meta=dict(data.get("meta") or {}), css=data.get("css"),
                stylesheets=[str(x) for x in (data.get("stylesheets") or [])],
                category=data.get("category"), output=data.get("output"), requires=data.get("requires"),
                tags=data["tags"] if data.get("tags") is not None else [], origin=data.get("origin", "canvas"))
    if data.get("layout") is not None:
        lay = data["layout"]
        d.layout = {"engine": lay} if isinstance(lay, str) else dict(lay)
    if data.get("grid") is not None:  # grid: {cols: [...], rows: [...], gutter: 20}; then cell: [c, r]
        d.grid(**data["grid"])
    _groups(d, data.get("groups") or [], None)
    for z in data.get("zones") or []:
        z = dict(z)
        if "class" in z:
            z["cls"] = z.pop("class")
        if z.get("band") is not None:  # band: [y0, y1]; the model pass sets y/h (and x/w unless given)
            z["band"] = tuple(z["band"])
            z = {"x": 0, "y": 0, "w": 0, "h": 0} | z
        if "cell" in z:
            label = z.pop("label", None)
            d.zone(label, **z)
            continue
        d._add_zone(Zone(**z))
    for n in data.get("nodes") or []:
        _node(d, n, data)
    for axis in ("row", "column"):  # containers: rows: [{x, y, gap, same_size, max_width, nodes: [...]}]
        for c in data.get(f"{axis}s") or []:  # or in a zone: rows: [{zone: <id>, align, cols, nodes: [...]}]
            c = dict(c)
            items = c.pop("nodes", None) or []
            unknown = set(c) - _CONTAINER_KEYS
            if unknown:
                raise ValueError(f"{d.id}: {axis} has unknown keys {sorted(unknown)}")
            zid = c.pop("zone", None)
            zone = next((z for z in d.zones if z.id == zid), None)
            if zid is not None and zone is None:
                raise ValueError(f"{d.id}: {axis} zone {zid!r} is not a zone id")
            with zone or nullcontext(), getattr(d, axis)(**c) as box:
                for item in items:
                    if isinstance(item, str):  # a node declared under nodes:
                        box.children.append(item)
                        if zone is not None and item not in zone.children:
                            zone.children.append(item)
                    else:
                        _node(d, item, data)
    for s in data.get("snakes") or []:  # snakes: [{steps, cols, y, h, x, w, gap, row_gap, zones, mode}]
        s = dict(s)
        unknown = set(s) - _SNAKE_KEYS
        if unknown:
            raise ValueError(f"{d.id}: snake has unknown keys {sorted(unknown)}")
        missing = {"steps", "cols", "y", "h"} - set(s)
        if missing:
            raise ValueError(f"{d.id}: snake is missing keys {sorted(missing)}")
        if s.get("zones") is not None:
            s["zones"] = [_cls(z) for z in s["zones"]]
        d.snake([_cls(st) for st in s.pop("steps")], s.pop("cols"), **s)
    for e in data.get("edges") or []:
        if isinstance(e, str):
            d.edges.append(parse_edge(e))
            continue
        e = dict(e)
        if "class" in e:
            e["cls"] = e.pop("class")
        src, dst = e.pop("from"), e.pop("to")
        d.edge(src, dst, **e)
    for c in data.get("align") or []:  # align: [{x: [a, b]}, {y: [a, c]}, {center: [a, b], axis: x}]
        if "x" in c:
            d.align_x(*c["x"])
        elif "y" in c:
            d.align_y(*c["y"])
        else:
            d.center_on(*c["center"], axis=c.get("axis", "both"))
    for b in data.get("bundles") or []:  # bundles: [{edges: [0, 1], trunk: right}] (edge indexes)
        d.bundle(list(b["edges"]), b.get("trunk"))
    for t in data.get("tables") or []:
        d.tables.append(Table(**t))
    _annotations(d, data.get("annotations") or {})
    if data.get("legend"):
        lg = data["legend"]
        items = [(i["color"], i["label"]) if isinstance(i, dict) else tuple(i) for i in lg["items"]]
        d.legend = Legend(x=lg["x"], y=lg["y"], items=items)
    from .autolayout import validate_groups

    validate_groups(d)
    return d


def _cls(item: Any) -> Any:
    """A snake step or zone dict with YAML's ``class`` key as the model's ``cls``."""
    if isinstance(item, dict) and "class" in item:
        item = dict(item)
        item["cls"] = item.pop("class")
    return item


def _step_ref(d: Diagram, on: Any) -> Any:
    """``"a -> b"`` is the first edge from a to b; anything else is a node id."""
    if isinstance(on, str) and "->" in on:
        a, _, b = on.partition("->")
        return (a.strip().partition(".")[0], b.strip().partition(".")[0])
    return on


def _on(item: dict, what: str, d: Diagram) -> Any:
    """The ``on:`` value; plain YAML 1.1 reads an unquoted ``on`` key as the boolean ``True``."""
    for key in ("on", True):
        if key in item:
            return item.pop(key)
    raise ValueError(f"{d.id}: {what} needs `on:` (a node id or \"a -> b\")")


def _annotations(d: Diagram, data: dict[str, Any]) -> None:
    """``annotations: {legend: {...}, steps: [...], callouts: [...]}`` through the Python builders (same checks)."""
    for n in d.nodes:
        variant = n.extra.get("variant")
        if variant is not None:
            if n.kind != "note" or variant not in NOTE_VARIANTS:
                raise ValueError(f"{d.id}: node {n.id!r} variant {variant!r}; notes take one of "
                                 f"{', '.join(NOTE_VARIANTS)}")
            if variant == "sticky":
                del n.extra["variant"]
    lg = data.get("legend")
    if lg is not None:
        lg = dict(lg) if isinstance(lg, dict) else {}
        d.add_legend(lg.get("items"), title=lg.get("title", "Legend"), position=lg.get("position"),
                     place=lg.get("place", "band"))
    for st in data.get("steps") or []:
        st = dict(st)
        d.step(st["text"], on=_step_ref(d, _on(st, "step", d)), n=st.get("n"))
    for c in data.get("callouts") or []:
        c = dict(c)
        d.callout(_on(c, "callout", d), c.pop("text"), title=c.pop("title", None), kind=c.pop("kind", "info"),
                  side=c.pop("side", "auto"), class_=c.pop("class", None), css=c.pop("css", None))
        if c:
            raise ValueError(f"{d.id}: callout has unknown keys {sorted(c)}")


def _dump_annotations(d: Diagram) -> dict[str, Any]:
    a, out = d.annotations, {}
    if a.legend:
        out["legend"] = {"title": a.legend.title}
        if a.legend.position is not None:
            out["legend"]["position"] = a.legend.position
        if a.legend.items is not None:
            out["legend"]["items"] = dict(a.legend.items)
    if a.steps:
        def ref(s):
            if s.node is not None:
                return s.node
            e = d.edges[s.edge]
            return f"{str(e.src).partition('.')[0]} -> {str(e.dst).partition('.')[0]}"
        out["steps"] = [{"on": ref(s), "n": s.n, "text": s.text} for s in a.steps]
    if a.callouts:
        out["callouts"] = [{k: v for k, v in (("on", c.target), ("text", c.text), ("title", c.title),
                                               ("kind", c.kind), ("side", c.side), ("class", c.cls),
                                               ("css", c.css)) if v is not None} for c in a.callouts]
    return out


def _tag_list(tags: Any) -> list:
    """A tags value as a list (one string is one tag); type errors surface in ``normalize_tags``."""
    return [tags] if isinstance(tags, str) else list(tags) if isinstance(tags, (list, tuple)) else [tags]


def _dir_defaults(folder: Path) -> dict[str, Any]:
    """``_defaults.yaml`` next to the specs supplies keys every diagram in the folder shares."""
    f = folder / "_defaults.yaml"
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}


class SpecError(ValueError):
    pass


def load_yaml(path: Path) -> list[Diagram]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SpecError(f"{path}: invalid YAML\n{exc}\nhint: inside {{...}} or [...], quote values "
                        "containing , : ? or #") from None
    docs = data if isinstance(data, list) else [data]
    base = _dir_defaults(path.parent)

    def merged(doc: dict) -> dict:
        out = {**base, **doc}
        if base.get("stylesheets") and doc.get("stylesheets"):  # folder sheets come first, then the spec's
            out["stylesheets"] = list(base["stylesheets"]) + list(doc["stylesheets"])
        if base.get("tags") is not None and doc.get("tags") is not None:  # folder tags join the spec's
            out["tags"] = _tag_list(base["tags"]) + _tag_list(doc["tags"])
        return out

    out = [from_dict(merged(doc), base_dir=path.parent) for doc in docs]
    for d in out:
        d.__dict__["_source"] = path  # the spec file (check --fix); not a dataclass field
    return out


def load_python(path: Path) -> list[Diagram]:
    """Diagrams of a Python spec: ``build() -> Diagram | list``, else ``diagrams`` or ``diagram``, else every
    ``Diagram`` the module keeps in a variable, in the order they were assigned."""
    import sys

    # helpers next to the spec (``_helpers.py``, ``dk.py``) are importable, like a script run from its folder
    added = str(path.parent.resolve()) not in sys.path
    if added:
        sys.path.insert(0, str(path.parent.resolve()))
    try:
        ns = runpy.run_path(str(path))
    finally:
        if added:
            sys.path.remove(str(path.parent.resolve()))
    if "build" in ns and callable(ns["build"]):
        got = ns["build"]()
    else:
        got = ns.get("diagrams", ns.get("diagram"))
    if got is None:  # no convention variable: any Diagram the script created and kept
        seen: set[int] = set()
        got = [v for k, v in ns.items() if not k.startswith("_") and isinstance(v, Diagram)
               and not (id(v) in seen or seen.add(id(v)))]
    if not got:
        raise ValueError(f"{path}: no diagram found — create one with Diagram(...), or define `diagrams` or `build()`")
    items = got if isinstance(got, (list, tuple)) else [got]
    base = _dir_defaults(path.parent)
    for d in items:
        d.base_dir = d.base_dir or path.parent
        for key in ("kicker", "source", "subtitle", "facts", "locale"):  # folder defaults fill what the script left unset
            if getattr(d, key) is None and base.get(key) is not None:
                setattr(d, key, base[key])
        if base.get("category") is not None and d.category is None:
            d.category = base["category"]
            d.__post_init__()  # validate the folder value like a declared one
        if base.get("tags") is not None:
            d.tags = normalize_tags(_tag_list(base["tags"]) + d.tags, d.id)
        if base.get("stylesheets"):  # folder stylesheets come before the script's own
            d.stylesheets = [str(x) for x in base["stylesheets"]] + [x for x in d.stylesheets
                                                                     if x not in base["stylesheets"]]
        d.__dict__["_source"] = path
    return list(items)


def load(path: str | Path) -> list[Diagram]:
    """Load one file or every ``*.yaml|*.yml|*.py`` spec in a directory (sorted)."""
    p = Path(path)
    if p.is_dir():
        out: list[Diagram] = []
        for f in sorted(p.iterdir()):
            if f.suffix in {".yaml", ".yml", ".py"} and not f.name.startswith("_"):
                out.extend(load(f))
        return out
    if p.suffix in {".yaml", ".yml"}:
        return load_yaml(p)
    if p.suffix == ".py":
        return load_python(p)
    raise ValueError(f"unsupported spec file {p}")


def _clean(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 1) if v != int(v) else int(v)
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    return v


def _dump_snakes(d: Diagram, changed) -> tuple[list[dict[str, Any]], set]:
    """``snakes:`` entries for ``dump``, plus the node ids, zone ids and edge ``id()``s each one regenerates.

    The snake pass places steps and row zones, so their x/y/w/h are left out. Chain edges are left out too when
    ``d.snake`` would recreate them as they are; otherwise (edge kwargs, an applied fix) the entry says
    ``chain: false`` and the edges stay in ``edges:``, at their indexes."""
    from .model import Node as _N, Zone as _Z

    out, made = [], set()
    for s in d.snakes:
        nodes = {n.id: n for n in d.nodes if n.id in s.nodes}
        zones = {z.id: z for z in d.zones if z.id in s.zones}
        steps = []
        for i in s.nodes:
            n = nodes[i]
            row = {"id": n.id} | ({"kind": n.kind} if n.kind != "box" else {})
            row |= changed(n, _N, skip=("id", "kind", "x", "y", "w", "h", "extra"))
            steps.append(row | {k: v for k, v in n.extra.items() if k != "in"})
        row = {"steps": steps, "cols": s.cols, "y": _clean(s.y), "h": _clean(s.h)}
        row |= {k: _clean(getattr(s, k)) for k, default in (("x", None), ("w", None), ("gap", 40), ("row_gap", 60),
                                                            ("mode", "boustrophedon")) if getattr(s, k) != default}
        if s.zones:
            row["zones"] = [{"id": z.id} | changed(z, _Z, skip=("id", "x", "y", "w", "h", "children"))
                            for z in (zones[i] for i in s.zones)]
        probe = Diagram(d.id, d.title)  # the chain edges ``d.snake`` would draw for this entry
        for i in s.nodes:  # endpoint kinds decide dashed object flows
            probe.add(nodes[i].kind, id=i)
        regen = [Edge(a, b, route="ortho" if (k + 1) % s.cols == 0 else None) for k, (a, b) in
                 enumerate(zip(s.nodes, s.nodes[1:]))]
        for e in regen:
            probe.edge(e.src, e.dst, route=e.route)
        chain = [next((e for e in d.edges if id(e) not in made and _ends(e) == (a, b)), None)
                 for a, b in zip(s.nodes, s.nodes[1:])]
        if all(c is not None for c in chain) and chain == probe.edges:
            made |= {id(e) for e in chain}
        else:
            row["chain"] = False
        made |= set(s.nodes) | set(s.zones)
        out.append(row)
    return out, made


def _ends(e: Edge) -> tuple[str, str]:
    return str(e.src).partition(".")[0], str(e.dst).partition(".")[0]


def dump(d: Diagram) -> dict[str, Any]:
    """An explicit, coordinate-complete spec for ``d`` (``layout``/``groups`` are dropped: zones carry them).

    Used by ``spinagram layout`` to freeze an automatic layout for hand-tuning.
    """
    from dataclasses import asdict, fields

    from .model import Container as _C, Edge as _E, Node as _N, Zone as _Z

    out: dict[str, Any] = {"id": d.id, "title": d.title}
    for k in ("subtitle", "source", "kicker", "facts", "locale", "output", "requires"):
        if getattr(d, k) is not None:
            out[k] = getattr(d, k)
    if d.category is not None:
        out["category"] = d.category
    if d.origin != "canvas":
        out["origin"] = d.origin
    if d.tags:
        out["tags"] = list(d.tags)
    if d.meta:
        out["meta"] = {k: v for k, v in d.meta.items() if not k.startswith("layout_") and k != "laid_out"} or None
        if out["meta"] is None:
            del out["meta"]

    def changed(obj, cls, skip=()) -> dict[str, Any]:
        base = {f.name: f.default for f in fields(cls) if f.default is not f.default_factory}  # type: ignore[misc]
        return {"class" if k == "cls" else k: _clean(v) for k, v in asdict(obj).items()
                if k not in skip and v not in (None, [], {}) and base.get(k, object()) != v}

    snakes, made = _dump_snakes(d, changed)  # the snakes, and the nodes/zones/edges they regenerate
    out["zones"] = [changed(z, _Z) | {"x": _clean(z.x), "y": _clean(z.y), "w": _clean(z.w), "h": _clean(z.h)}
                    for z in d.zones if z.id not in made]
    nodes = []
    for n in d.nodes:
        if n.id in made:
            continue
        row = {"id": n.id, "kind": n.kind} if n.kind != "box" else {"id": n.id}
        row["at"] = [_clean(n.x), _clean(n.y)] + ([_clean(n.w), _clean(n.h)] if n.w or n.h else [])
        row |= changed(n, _N, skip=("id", "kind", "x", "y", "w", "h", "extra"))
        row |= {k: v for k, v in n.extra.items() if k != "in"}
        nodes.append(row)
    out["nodes"] = nodes
    if snakes:
        out["snakes"] = snakes
    edges = []
    for e in d.edges:
        if id(e) in made:
            continue
        row = {"from": _clean(e.src), "to": _clean(e.dst)}
        row |= changed(e, _E, skip=("src", "dst"))
        edges.append(row)
    out["edges"] = edges
    for axis in ("row", "column"):  # containers keep their members as node ids
        rows = [changed(c, _C, skip=("axis", "children")) | {"nodes": list(c.children)}
                for c in d.containers if c.axis == axis]
        if rows:
            out[f"{axis}s"] = rows
    if d.tables:
        out["tables"] = [changed(t, type(t)) | {"x": t.x, "y": t.y} for t in d.tables]
    if d.legend:
        out["legend"] = {"x": d.legend.x, "y": d.legend.y, "items": [list(i) for i in d.legend.items]}
    if d.annotations:
        out["annotations"] = _dump_annotations(d)
    return {k: v for k, v in out.items() if v not in ([],)}


__all__ = ["load", "from_dict", "dump", "Edge"]
