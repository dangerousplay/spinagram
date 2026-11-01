"""Edit a diagram's YAML text through the Rust edit operations (``spinagram._core``).

``apply_ops`` patches the text minimally: bytes outside the edited ranges (comments, blank lines, key order,
flow or block style) are unchanged, and a batch applies completely or not at all. ``srcmap`` gives the byte range
of the YAML entry of each element. The browser calls the same Rust code through WebAssembly.

Operations are dicts (``"op"`` names the kind)::

    {"op": "move", "id": "a", "x": 100, "y": 40}          {"op": "resize", "id": "a", "w": 160, "h": 80}
    {"op": "rename", "id": "a", "title": "New title"}      {"op": "delete", "id": "a"}
    {"op": "add_node", "id": "n", "title": "T", "x": 0, "y": 0, "w": 120, "h": 60}   (kind, title, geometry optional)
    {"op": "connect", "from": "a", "to": "b", "label": "calls"}   {"op": "disconnect", "from": "a", "to": "b"}

The core has no pure-Python twin of these operations, so ``SPINAGRAM_RUST=0`` does not switch them off.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from . import rust


class EditError(ValueError):
    """An operation was rejected; the message is the Rust reason, naming the operation that failed."""


def _core():
    mod = rust._load()
    if mod is None:
        raise EditError("the Rust core (spinagram._core) is required for edit operations")
    return mod


def apply_ops(yaml_text: str, ops: Iterable[Mapping[str, Any]]) -> str:
    """The YAML text with ``ops`` applied as one batch; raises ``EditError`` and changes nothing when one is invalid."""
    try:
        return _core().apply_ops(yaml_text, json.dumps(list(ops)))
    except ValueError as exc:
        raise EditError(str(exc)) from None


def srcmap(yaml_text: str) -> dict[str, tuple[int, int]]:
    """``{id: (start, end)}``: the UTF-8 byte range of each node's, zone's and edge's (``e0``, ``e1``, ...) entry."""
    try:
        return _core().yaml_srcmap(yaml_text)
    except ValueError as exc:
        raise EditError(str(exc)) from None
