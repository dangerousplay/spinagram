"""Load diagrams from YAML files and Python modules."""
from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

import yaml

from .model import Diagram, Edge, Group, Legend, Table, Zone, parse_edge

_NODE_KEYS = {"id", "kind", "x", "y", "w", "h", "title", "text", "lines", "style", "icon", "icon_size", "align",
              "title_size", "body_size", "radius", "dashed", "color", "in", "class", "css"}
_NODE_EXTRA = {"weight", "font"}  # kind: text options
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


def from_dict(data: dict[str, Any], base_dir: Path | None = None) -> Diagram:
    for req in ("id", "title"):
        if req not in data:
            raise ValueError(f"diagram is missing required key {req!r}")
    d = Diagram(id=str(data["id"]), title=str(data["title"]), subtitle=data.get("subtitle"),
                source=data.get("source"), kicker=data.get("kicker"), base_dir=base_dir,
                facts=data.get("facts"), locale=data.get("locale"),
                meta=dict(data.get("meta") or {}), css=data.get("css"),
                stylesheets=[str(x) for x in (data.get("stylesheets") or [])])
    if data.get("layout") is not None:
        lay = data["layout"]
        d.layout = {"engine": lay} if isinstance(lay, str) else dict(lay)
    _groups(d, data.get("groups") or [], None)
    for z in data.get("zones") or []:
        d.zones.append(Zone(**z))
    for n in data.get("nodes") or []:
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
        node = d.add(kind, title, **n)
        node.extra.update(extra)
        if parent is not None:
            g = next((g for g in d.groups if g.id == parent), None)
            if g is None:
                raise ValueError(f"{data['id']}: node {node.id!r} is `in` unknown group {parent!r}")
            g.children.append(node.id)
    for e in data.get("edges") or []:
        if isinstance(e, str):
            d.edges.append(parse_edge(e))
            continue
        e = dict(e)
        if "class" in e:
            e["cls"] = e.pop("class")
        src, dst = e.pop("from"), e.pop("to")
        d.edge(src, dst, **e)
    for t in data.get("tables") or []:
        d.tables.append(Table(**t))
    if data.get("legend"):
        lg = data["legend"]
        items = [(i["color"], i["label"]) if isinstance(i, dict) else tuple(i) for i in lg["items"]]
        d.legend = Legend(x=lg["x"], y=lg["y"], items=items)
    from .autolayout import validate_groups

    validate_groups(d)
    return d


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
    return [from_dict({**base, **doc}, base_dir=path.parent) for doc in docs]


def load_python(path: Path) -> list[Diagram]:
    """A Python spec defines ``diagram``, ``diagrams`` or ``build() -> Diagram | list``."""
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
    if got is None:
        raise ValueError(f"{path}: define `diagram`, `diagrams` or `build()`")
    items = got if isinstance(got, (list, tuple)) else [got]
    base = _dir_defaults(path.parent)
    for d in items:
        d.base_dir = d.base_dir or path.parent
        for key in ("kicker", "source", "subtitle", "facts", "locale"):  # folder defaults fill what the script left unset
            if getattr(d, key) is None and base.get(key) is not None:
                setattr(d, key, base[key])
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


def dump(d: Diagram) -> dict[str, Any]:
    """An explicit, coordinate-complete spec for ``d`` (``layout``/``groups`` are dropped: zones carry them).

    Used by ``spinagram layout`` to freeze an automatic layout for hand-tuning.
    """
    from dataclasses import asdict, fields

    from .model import Edge as _E, Node as _N, Zone as _Z

    out: dict[str, Any] = {"id": d.id, "title": d.title}
    for k in ("subtitle", "source", "kicker", "facts", "locale"):
        if getattr(d, k) is not None:
            out[k] = getattr(d, k)
    if d.meta:
        out["meta"] = {k: v for k, v in d.meta.items() if not k.startswith("layout_")} or None
        if out["meta"] is None:
            del out["meta"]

    def changed(obj, cls, skip=()) -> dict[str, Any]:
        base = {f.name: f.default for f in fields(cls) if f.default is not f.default_factory}  # type: ignore[misc]
        return {k: _clean(v) for k, v in asdict(obj).items()
                if k not in skip and v not in (None, [], {}) and base.get(k, object()) != v}

    out["zones"] = [changed(z, _Z) | {"x": _clean(z.x), "y": _clean(z.y), "w": _clean(z.w), "h": _clean(z.h)}
                    for z in d.zones]
    nodes = []
    for n in d.nodes:
        row = {"id": n.id, "kind": n.kind} if n.kind != "box" else {"id": n.id}
        row["at"] = [_clean(n.x), _clean(n.y)] + ([_clean(n.w), _clean(n.h)] if n.w or n.h else [])
        row |= changed(n, _N, skip=("id", "kind", "x", "y", "w", "h", "extra"))
        row |= {k: v for k, v in n.extra.items() if k != "in"}
        nodes.append(row)
    out["nodes"] = nodes
    edges = []
    for e in d.edges:
        row = {"from": _clean(e.src), "to": _clean(e.dst)}
        row |= changed(e, _E, skip=("src", "dst"))
        edges.append(row)
    out["edges"] = edges
    if d.tables:
        out["tables"] = [changed(t, type(t)) | {"x": t.x, "y": t.y} for t in d.tables]
    if d.legend:
        out["legend"] = {"x": d.legend.x, "y": d.legend.y, "items": [list(i) for i in d.legend.items]}
    return {k: v for k, v in out.items() if v not in ([],)}


__all__ = ["load", "from_dict", "dump", "Edge"]
