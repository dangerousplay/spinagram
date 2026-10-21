"""Edge label placement (layout-engine EDG-01..06)."""
import pytest

from spinagram.engine.labels import candidates

LH = 30  # label height → side offset 15 + 6 = 21
CANDIDATE_SCENARIOS = [
    ("straight-right", [(0, 0), (1000, 0)],
     [(500, 0), (300, 0), (700, 0), (150, 0), (850, 0),
      (500, -21), (500, 21), (300, -21), (300, 21), (700, -21), (700, 21), (150, -21), (150, 21), (850, -21),
      (850, 21)]),
    ("straight-down", [(0, 0), (0, 1000)],
     [(0, 500), (0, 300), (0, 700), (0, 150), (0, 850),
      (21, 500), (-21, 500), (21, 300), (-21, 300), (21, 700), (-21, 700), (21, 150), (-21, 150), (21, 850),
      (-21, 850)]),
    ("straight-left", [(1000, 0), (0, 0)],
     [(500, 0), (700, 0), (300, 0), (850, 0), (150, 0),
      (500, 21), (500, -21), (700, 21), (700, -21), (300, 21), (300, -21), (850, 21), (850, -21), (150, 21),
      (150, -21)]),
    ("poly-elbow", [(0, 0), (1000, 0), (1000, 1000)],
     [(1000, 0), (600, 0), (1000, 400), (300, 0), (1000, 700),
      (1000, -21), (1000, 21), (600, -21), (600, 21), (1021, 400), (979, 400), (300, -21), (300, 21),
      (1021, 700), (979, 700)]),
]


@pytest.mark.parametrize("points,expected", [s[1:] for s in CANDIDATE_SCENARIOS], ids=[s[0] for s in CANDIDATE_SCENARIOS])
def test_candidates_in_spec_order(points, expected):  # EDG-01
    got = candidates(points, LH)
    assert len(got) == 15
    assert [tuple(round(v, 6) for v in p) for p in got] == [tuple(float(v) for v in p) for p in expected]


def test_curve_candidates_follow_the_sampled_path():  # EDG-01 on a quadratic curve
    from spinagram.qa import polyline
    from spinagram.scene import Connector
    c = Connector("e0", [(0, 0), (500, -400), (1000, 0)], "curve", "#000", 2)
    got = candidates(polyline(c), LH)
    assert got[0][0] == pytest.approx(500, abs=1) and got[0][1] == pytest.approx(-200, abs=2)  # curve apex
    assert got[1][0] < 500 < got[2][0]


# placement pass (EDG-02..05) ---------------------------------------------------------------------------------
from spinagram import Diagram, Theme, build_scene  # noqa: E402
from spinagram.engine.labels import ARROWHEAD, overlap  # noqa: E402
from spinagram.scene import Connector, Shape  # noqa: E402

THEME = Theme.load("default")


def _rect(s):
    return (s.x, s.y, s.w, s.h)


def _label_scene(build):
    d = Diagram("L", "Labels")
    build(d)
    sc = build_scene(d, THEME)
    return sc, {i.id: i for i in sc.items if isinstance(i, (Shape, Connector))}


def test_golden_label_change_is_the_centring():  # the single intended golden change (T19)
    def build(d):
        a = d.box("A", x=100, y=250, w=300, h=140, style="dark")
        b = d.box("B", x=700, y=250, w=300, h=140)
        d.zone("Zone", x=60, y=200, w=1000, h=260)
        d.edge(a.right, b.left, "go", dashed=True)
    _, by = _label_scene(build)
    lab = by["e0"].label
    assert (lab.x + lab.w / 2, lab.y + lab.h / 2) == pytest.approx((550, 320))


def _boxes(d, gap):
    """Two boxes side by side with ``gap`` px between them and a third box right above the gap."""
    a = d.box("A", id="a", x=200, y=400, w=200, h=100)
    b = d.box("B", id="b", x=400 + gap, y=400, w=200, h=100)
    return a, b


PLACEMENT_SCENARIOS = [
    # id, builder, expected candidate index (0 = midpoint; 5.. = beside)
    ("free-midpoint", lambda d: d.edge(*_boxes(d, 400), "HTTPS"), 0),
    ("blocker-on-midpoint", lambda d: (d.edge(*_boxes(d, 400), "HTTPS"),
                                       d.box("X", id="x", x=560, y=420, w=80, h=60)), 1),
    ("long-label-short-gap", lambda d: d.edge(*_boxes(d, 60), "replication"), None),
]


@pytest.mark.parametrize("build,index", [s[1:] for s in PLACEMENT_SCENARIOS], ids=[s[0] for s in PLACEMENT_SCENARIOS])
def test_first_free_candidate_wins(build, index):  # EDG-02, EDG-03
    sc, by = _label_scene(build)
    c = by["e0"]
    lab = c.label
    nodes = [_rect(s) for s in by.values() if isinstance(s, Shape) and s.role == "node"]
    free = all(overlap(_rect(lab), n) < 0.5 for n in nodes)
    if index is not None:
        want = candidates(c.points, lab.h)[index]
        assert (lab.x + lab.w / 2, lab.y + lab.h / 2) == pytest.approx(want)
        assert free
    else:  # EDG-04: nothing free → least overlap, reported with the number of candidates
        issues = [a for a in sc.annotation_issues if a[0] == "e0" and a[1] == "label-collision"]
        assert not free and issues and "15 candidates tried" in issues[0][2]


OBSTACLE_SCENARIOS = [
    # id, extra element drawn over the midpoint candidate
    ("node", lambda d: d.box("X", id="x", x=560, y=420, w=80, h=60)),
    ("zone-header", lambda d: d.zone("Header zone", x=440, y=440, w=500, h=200, icon=None)),
    ("other-label", lambda d: d.edge((450, 520), (650, 400), "other", label_at=(550, 458))),
]


@pytest.mark.parametrize("extra", [s[1] for s in OBSTACLE_SCENARIOS], ids=[s[0] for s in OBSTACLE_SCENARIOS])
def test_label_avoids_each_obstacle_kind(extra):  # EDG-02
    def build(d):
        d.edge(*_boxes(d, 400), "HTTPS")
        extra(d)
    sc, by = _label_scene(build)
    lab = _rect(by["e0"].label)
    assert all(overlap(lab, h) < 0.5 for h in sc.zone_headers.values())
    for k, s in by.items():
        if isinstance(s, Shape) and s.role == "node":
            assert overlap(lab, _rect(s)) < 0.5
        if isinstance(s, Connector) and k != "e0" and s.label is not None:
            assert overlap(lab, _rect(s.label)) < 0.5


def test_label_avoids_its_own_arrowhead():  # EDG-02: last 14 px of the edge
    def build(d):
        d.box("A", id="a", x=200, y=200, w=200, h=100)
        d.box("B", id="b", x=200, y=420, w=200, h=100)
        d.edge("a.bottom", "b.top", "a long label here")
    _, by = _label_scene(build)
    c = by["e0"]
    (ex, ey) = c.points[-1]
    head = (ex - 6, ey - ARROWHEAD - 6, 12, ARROWHEAD + 6)
    assert overlap(_rect(c.label), head) < 0.5


def test_label_stays_inside_canvas_margin():  # EDG-02: canvas margin (80 px)
    def build(d):
        d.edge((300, 90), (900, 90), "near the top")
    _, by = _label_scene(build)
    c = by["e0"]
    lab = c.label
    assert lab.y >= 80
    assert (lab.x + lab.w / 2, lab.y + lab.h / 2) == pytest.approx(candidates(c.points, lab.h)[6])  # below mid


def test_label_at_is_kept():  # EDG-05
    def build(d):
        d.edge(*_boxes(d, 400), "HTTPS", label_at=(300, 450))   # deliberately over box a
    _, by = _label_scene(build)
    lab = by["e0"].label
    assert lab.x + lab.w / 2 == pytest.approx(300)


# random short edges and determinism (EDG-06, roadmap E1 acceptance) -----------------------------------------
import random  # noqa: E402

from spinagram.engine.labels import arrowheads, outside  # noqa: E402
from spinagram.qa import polyline  # noqa: E402

WORDS = ["HTTPS", "NFS", "IP da VM", "replicação", "logs", "443", "gRPC stream", "IP NAT", "sync"]


def _random_diagram(seed: int) -> Diagram:
    rnd = random.Random(seed)
    d = Diagram(f"R{seed}", "Random")
    boxes = []
    for r in range(4):
        for c in range(5):
            if rnd.random() < 0.8:
                boxes.append(d.box(f"N{r}{c}", id=f"n{r}{c}", x=150 + c * 330 + rnd.randint(0, 40),
                                   y=180 + r * 210 + rnd.randint(0, 30), w=200, h=90))
    for _ in range(10):  # short edges between neighbours
        a = rnd.choice(boxes)
        near = sorted(boxes, key=lambda b: abs(b.x - a.x) + abs(b.y - a.y))[1:4]
        d.edge(a, rnd.choice(near), rnd.choice(WORDS))
    return d


def _check_placement(sc):
    """Whenever a candidate was free (against the same obstacle set, in edge order), the label is free."""
    m = (THEME.get("canvas") or {}).get("margin", 80)
    bounds = (m, m, sc.width - 2 * m, sc.height - 2 * m)
    conns = [i for i in sc.items if isinstance(i, Connector)]
    obstacles = [_rect(s) for s in sc.items if isinstance(s, Shape) and s.role == "node"]
    obstacles += list(sc.zone_headers.values())
    heads = arrowheads(conns)
    placed = []
    for c in conns:
        lab = c.label

        def cost(r):
            return sum(overlap(r, o) for o in (*obstacles, *heads, *placed)) + outside(r, bounds)
        any_free = any(cost((x - lab.w / 2, y - lab.h / 2, lab.w, lab.h)) < 0.5
                       for x, y in candidates(polyline(c), lab.h))
        if any_free:
            assert cost(_rect(lab)) < 0.5, c.id
        placed.append(_rect(lab))


@pytest.mark.parametrize("seed", range(20), ids=lambda s: f"seed{s}")
def test_random_short_edges_labels_never_hit_obstacles(seed):
    _check_placement(build_scene(_random_diagram(seed), THEME))


DETERMINISM = """
import hashlib, json, sys
sys.path.insert(0, {tests!r})
from test_engine_labels import _random_diagram, THEME
from spinagram import build_scene
from spinagram.scene import Connector
out = []
for seed in range(5):
    sc = build_scene(_random_diagram(seed), THEME)
    out += [(c.id, round(c.label.x, 3), round(c.label.y, 3)) for c in sc.items if isinstance(c, Connector)]
print(hashlib.sha256(json.dumps(out).encode()).hexdigest())
"""


def test_label_positions_identical_across_hash_seeds():  # EDG-06
    import os
    import subprocess
    import sys
    from pathlib import Path
    code = DETERMINISM.format(tests=str(Path(__file__).parent))
    hashes = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                             env={**os.environ, "PYTHONHASHSEED": str(s)}).stdout.strip() for s in range(5)}
    assert len(hashes) == 1 and len(hashes.pop()) == 64
