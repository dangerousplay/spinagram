"""Rust router vs Python router (ROUTE-04..09) and dispatch (ROUTE-01..03)."""
import importlib

import pytest

from spinagram.engine.route import Crossings

pyroute = importlib.import_module("spinagram.autolayout.route")  # the package re-exports a `route` function


@pytest.fixture
def python_router(monkeypatch):
    """The Python router, whatever the environment says about the Rust core."""
    monkeypatch.setattr(pyroute, "_CORE", None, raising=False)


# binding parity ---------------------------------------------------------------------------------------------------
class TestBinding:
    @pytest.fixture(autouse=True)
    def core(self):
        self.core = pytest.importorskip("spinagram._core")

    def check(self, python_router, src, dst, obstacles=(), *, margin=14.0, sides=(None, None), busy=None,
              crossing=None, guides=(), fracs=(None, None)):
        expected = pyroute.route(src, dst, list(obstacles), margin=margin, sides=sides, busy=busy, penalty=crossing,
                                 guides=list(guides), fracs=fracs)
        busy = busy or {}
        got = self.core.route(src, dst, list(obstacles), margin, sides, sorted(busy.get(src, ())),
                              sorted(busy.get(dst, ())), None if crossing is None else (crossing.cost, crossing.drawn),
                              list(guides), fracs)
        assert got == expected
        return got

    def test_boxed_in_gives_the_elbow(self, python_router):  # ROUTE-05
        got = self.check(python_router, (100, 100, 40, 40), (100, 200, 40, 40), [(50, 50, 200, 250)])
        assert got == [(120, 140), (120, 170), (120, 170), (120, 200)]

    def test_stub_inside_obstacle_rejects_side_pair(self, python_router):  # ROUTE-06
        got = self.check(python_router, (0, 0, 40, 40), (300, 0, 40, 40), [(45, 0, 40, 40)],
                         sides=("right", "left"))
        assert got == [(20, 40), (20, 20), (320, 20), (320, 0)]

    def test_busy_side_costs_extra(self, python_router):  # ROUTE-07
        src, dst = (0, 0, 40, 40), (300, 0, 40, 40)
        free = self.check(python_router, src, dst)
        busy = self.check(python_router, src, dst, busy={src: {"right"}})
        assert free[0] == (40, 20) and busy[0] != (40, 20)
        self.check(python_router, src, dst, busy={src: {"right"}, dst: {"left", "top"}})

    def test_crossing_penalty(self, python_router):  # ROUTE-08
        src, dst = (0, 0, 40, 40), (200, 0, 40, 40)
        wall = ((120, -100), (120, 100))
        guides = [(106, -114), (134, 114)]
        got = self.check(python_router, src, dst, crossing=Crossings(1000.0, [wall]), guides=guides)
        assert len(got) > 2
        self.check(python_router, src, dst, crossing=Crossings(0.0, [wall]), guides=guides)

    def test_fraction_of_side(self, python_router):  # ROUTE-09
        got = self.check(python_router, (0, 0, 100, 40), (0, 200, 100, 40), sides=("bottom", "top"),
                         fracs=(0.2, None))
        assert got[0] == (20, 40)
        self.check(python_router, (0, 0, 100, 40), (400, 200, 100, 40), fracs=(0.2, 0.75))

    def test_fixed_sides(self, python_router):  # edge case: sides fix the ends
        self.check(python_router, (0, 0, 80, 40), (300, 100, 80, 40), [(150, 40, 60, 80)], sides=("top", "left"))
        self.check(python_router, (0, 0, 80, 40), (300, 100, 80, 40), sides=(None, "bottom"))

    def test_empty_guides(self, python_router):  # edge case: grid from obstacles and stubs only
        self.check(python_router, (0, 0, 80, 40), (300, 100, 80, 40), [(150, 20, 60, 100)], guides=[])

    def test_obstacles_containing_src_and_dst(self, python_router):  # edge case
        src, dst = (0, 0, 80, 40), (300, 100, 80, 40)
        self.check(python_router, src, dst, [src, dst, (150, 20, 60, 100)])


# dispatch ---------------------------------------------------------------------------------------------------------
class FakeCore:
    def __init__(self):
        self.calls = []

    def route(self, *args):
        self.calls.append(args)
        return [(1.0, 2.0), (3.0, 4.0)]


SRC, DST = (0, 0, 40, 40), (300, 0, 40, 40)


@pytest.fixture
def fake(monkeypatch):
    f = FakeCore()
    monkeypatch.setattr(pyroute, "_CORE", f, raising=False)
    return f


def test_core_active_without_penalty_uses_the_core(fake):  # ROUTE-01 (None)
    assert pyroute.route(SRC, DST, []) == [(1.0, 2.0), (3.0, 4.0)]
    assert len(fake.calls) == 1
    assert fake.calls[0][-3] is None  # crossing


def test_core_active_with_crossings_passes_cost_and_drawn(fake):  # ROUTE-01 (Crossings)
    drawn = [((120, -100), (120, 100))]
    assert pyroute.route(SRC, DST, [], penalty=Crossings(120.0, drawn)) == [(1.0, 2.0), (3.0, 4.0)]
    assert fake.calls[0][-3] == (120.0, drawn)


def test_core_active_passes_busy_sides_of_src_and_dst(fake):  # ROUTE-01 (busy lookup)
    pyroute.route(SRC, DST, [], busy={SRC: {"right"}, DST: {"left"}, (9, 9, 9, 9): {"top"}})
    args = fake.calls[0]
    assert (args[5], args[6]) == (["right"], ["left"])


def test_plain_callable_penalty_stays_in_python(fake):  # ROUTE-02
    got = pyroute.route(SRC, DST, [], penalty=lambda p, q: 0.0)
    assert fake.calls == []
    assert got == [(40.0, 20.0), (300.0, 20.0)]


def test_core_inactive_never_calls_the_core(python_router):  # ROUTE-03
    got = pyroute.route(SRC, DST, [], penalty=Crossings(120.0, []))
    assert got == [(40.0, 20.0), (300.0, 20.0)]
