"""Built-in helpers: node lookup and distribute (HLP-01..03)."""
from __future__ import annotations

import pytest

from spinagram import Diagram


def _d():
    d = Diagram("H", "Helpers")
    d.box("API", id="api", x=0, y=0, w=100, h=50)
    d.zone("VPC", id="vpc", x=0, y=0, w=500, h=300)
    d.zone("Shared", id="both", x=0, y=0, w=500, h=300)
    d.box("Both", id="both", x=0, y=0, w=100, h=50)
    return d


LOOKUPS = [  # (id, key, expected (type, id))
    ("node", "api", ("Node", "api")),
    ("zone", "vpc", ("Zone", "vpc")),
    ("node-before-zone", "both", ("Node", "both")),
]


@pytest.mark.parametrize("key,want", [lk[1:] for lk in LOOKUPS], ids=[lk[0] for lk in LOOKUPS])
def test_lookup(key, want):
    got = _d()[key]
    assert (type(got).__name__, got.id) == want


def test_lookup_returns_the_object_itself():
    d = _d()
    assert d["api"] is d.nodes[0] and d["vpc"] is d.zones[0]


def test_lookup_missing():
    with pytest.raises(KeyError) as err:
        _d()["nope"]
    assert err.value.args[0] == "H: no node or zone 'nope'"


DISTRIBUTE = [  # (id, n, w, gap, within, expected xs, expected w (no-w form) or None)
    # with w: block n·w + (n−1)·gap centred in within
    ("w-centred", 3, 200, 40, (80, 1840), [620, 860, 1100], None),      # block 680, start 80 + (1760 − 680) / 2
    ("w-exact-fit", 4, 400, 20, (80, 1740), [80, 500, 920, 1340], None),  # block 1660 = width
    ("w-one", 1, 300, 50, (0, 1000), [350], None),
    ("w-no-gap", 2, 100, 0, (0, 400), [100, 200], None),
    # without w: fill within, w = (width − (n−1)·gap) / n
    ("fill", 4, None, 40, (80, 1840), [80, 530, 980, 1430], 410),       # (1760 − 120) / 4 = 410
    ("fill-one", 1, None, 40, (100, 500), [100], 400),
    ("fill-no-gap", 3, None, 0, (0, 900), [0, 300, 600], 300),
    ("fill-fraction", 3, None, 10, (0, 100), [0, 36.666667, 73.333333], 26.666667),
]


@pytest.mark.parametrize("n,w,gap,within,xs,width", [t[1:] for t in DISTRIBUTE], ids=[t[0] for t in DISTRIBUTE])
def test_distribute(n, w, gap, within, xs, width):
    got = Diagram("H", "Helpers").distribute(n, w, gap, within=within)
    if width is None:
        assert got == pytest.approx(xs)
    else:
        assert got[0] == pytest.approx(xs) and got[1] == pytest.approx(width)


def test_distribute_keyword_form():
    assert Diagram("H", "Helpers").distribute(2, w=100, gap=20, within=(0, 420)) == [100, 220]


ERRORS = [  # (id, n, w, gap, within, message)
    ("n-zero", 0, 100, 0, (0, 500), "H: distribute n 0; use 1 or more"),
    ("n-negative", -2, None, 0, (0, 500), "H: distribute n -2; use 1 or more"),
    ("w-too-wide", 3, 200, 40, (0, 679), "H: distribute block 680px does not fit within (0, 679) (679px)"),
    ("gaps-fill-within", 3, None, 300, (0, 600), "H: distribute block 600px does not fit within (0, 600) (600px)"),
    ("empty-within", 1, None, 0, (500, 500), "H: distribute block 0px does not fit within (500, 500) (0px)"),
]


@pytest.mark.parametrize("n,w,gap,within,msg", [e[1:] for e in ERRORS], ids=[e[0] for e in ERRORS])
def test_distribute_errors(n, w, gap, within, msg):
    with pytest.raises(ValueError) as err:
        Diagram("H", "Helpers").distribute(n, w, gap, within=within)
    assert str(err.value) == msg


def test_distribute_needs_within():
    with pytest.raises(TypeError):
        Diagram("H", "Helpers").distribute(3, 100)  # type: ignore[call-arg]


def test_lookup_does_not_make_a_diagram_iterable():
    with pytest.raises(TypeError):
        list(_d())
