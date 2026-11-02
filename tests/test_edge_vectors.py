"""The shared edge vectors (rust/schema/edge_vectors.json) against the Python loader; cargo test runs the same file."""

import json
from pathlib import Path

import pytest

from spinagram.engine.endpoints import _split
from spinagram.model import parse_edge

VECTORS = json.loads((Path(__file__).parent.parent / "rust" / "schema" / "edge_vectors.json").read_text(encoding="utf-8"))
SIDES = {"top", "bottom", "left", "right"}


def test_the_table_is_not_trivial():
    assert len(VECTORS["edges"]) >= 30
    assert any(v["parsed"] is None for v in VECTORS["edges"])
    assert any(v["parsed"] is not None for v in VECTORS["edges"])


@pytest.mark.parametrize("case", VECTORS["edges"], ids=lambda c: repr(c["input"]))
def test_parse_edge_matches_the_vector(case):
    want = case["parsed"]
    if want is None:
        with pytest.raises(ValueError):
            parse_edge(case["input"])
        return
    e = parse_edge(case["input"])
    assert {"src": e.src, "dst": e.dst, "label": e.label, "arrow": e.arrow} == want


@pytest.mark.parametrize("case", VECTORS["endpoints"], ids=lambda c: repr(c["input"]))
def test_endpoint_split_matches_the_vector(case):
    name, side, frac = _split(case["input"])
    zone = name.startswith("zone:")
    raw = {"target": "zone" if zone else "node", "id": name[5:] if zone else name, "side": side, "frac": frac}
    assert raw == case["raw"]
    typed = case["typed"]
    if typed is not None:
        assert typed["id"] and (side == "" or side in SIDES)
        assert typed["side"] == (side or None)
        assert typed["frac"] == (float(frac) if frac else None)
