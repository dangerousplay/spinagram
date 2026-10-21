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
