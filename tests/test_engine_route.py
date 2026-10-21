"""Routing: crossing penalty, ortho routes, crossings check, bundles (layout-engine EDG-13..21)."""
import pytest

from spinagram.autolayout.route import route


def _crosses(p, q, a, b):
    """Strict crossing of an axis-aligned segment p→q with a perpendicular one a→b."""
    if p[0] == q[0] and a[1] == b[1]:
        return min(a[0], b[0]) < p[0] < max(a[0], b[0]) and min(p[1], q[1]) < a[1] < max(p[1], q[1])
    if p[1] == q[1] and a[0] == b[0]:
        return min(p[0], q[0]) < a[0] < max(p[0], q[0]) and min(a[1], b[1]) < p[1] < max(a[1], b[1])
    return False


WALL = ((500, 400), (500, 600))     # an edge already routed: vertical, between the two boxes
SRC, DST = (100, 475, 100, 50), (800, 475, 100, 50)


def _n_cross(pts):
    return sum(_crosses(p, q, *WALL) for p, q in zip(pts, pts[1:]))


@pytest.mark.parametrize("cost,crosses", [(120, 1), (2000, 0)], ids=["cheap-crossing", "costly-crossing"])
def test_crossing_penalty_trades_against_detours(cost, crosses):  # EDG-18
    pts = route(SRC, DST, [SRC, DST], penalty=lambda a, b: cost * _crosses(a, b, *WALL),
                guides=[(500 - 14, 400 - 14), (500 + 14, 600 + 14)])
    assert _n_cross(pts) == crosses
    assert _on_outline(pts[0], SRC) and _on_outline(pts[-1], DST)


def _on_outline(p, b):
    x, y, w, h = b
    return (p[0] in (x, x + w) and y <= p[1] <= y + h) or (p[1] in (y, y + h) and x <= p[0] <= x + w)


def test_without_penalty_routes_are_unchanged():  # default stays identical (layered goldens)
    assert route(SRC, DST, [SRC, DST]) == route(SRC, DST, [SRC, DST], penalty=None, guides=[])
