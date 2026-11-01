"""Routing parity and speed: compare the Rust router with the Python router.

Records every `route()` call made while building the examples, adds seeded random scenarios, replays each
through both routers and requires identical point lists. Exits 1 on any difference. Run from anywhere after
installing the wheel:
    uv run --all-extras --no-sync python rust/bench/route_parity.py
"""
from __future__ import annotations

import copy
import importlib
import os
import random
import sys
import tempfile
import time
from pathlib import Path

import spinagram_core as core

from spinagram import api, cli
from spinagram.engine import route as engine_route
from spinagram.theme import Theme

ROOT = Path(__file__).resolve().parents[2]
pyroute = importlib.import_module("spinagram.autolayout.route")
SIDES = ["top", "bottom", "left", "right"]
RANDOM_SCENARIOS = 2500
SEED = 20240601


def targets() -> list[str]:
    """The same targets as render_all.sh."""
    out = []
    for p in sorted((ROOT / "examples").iterdir()):
        if p.suffix in (".py", ".yaml"):
            out.append(f"examples/{p.name}")
        elif p.is_dir():
            out.append(f"examples/{p.name}/")
    return out + ["docs/diagrams/"]


def record_examples() -> list[tuple[tuple, dict]]:
    """Every route() call made while building all examples (arguments copied at call time)."""
    calls: list[tuple[tuple, dict]] = []
    original = pyroute.route

    def recorder(*args, **kw):
        busy = kw.get("busy")
        snap = dict(kw, guides=list(kw.get("guides", ())))
        if busy is not None:
            snap["busy"] = {k: set(v) for k, v in busy.items()}
        calls.append((copy.deepcopy(args), snap))
        return original(*args, **kw)

    holders = [pyroute, engine_route, importlib.import_module("spinagram.autolayout"),
               importlib.import_module("spinagram.autolayout.engines.layered")]
    saved = [(m, m.route) for m in holders]
    for m in holders:
        m.route = recorder
    pyroute._CORE = None
    os.chdir(ROOT)
    try:
        out = tempfile.mkdtemp()
        for t in targets():
            api.render(cli._collect([t], None), f"{out}/x", theme=Theme.load(None), formats=["svg"], gallery=False)
    finally:
        for m, fn in saved:
            m.route = fn
    return calls


def rand_box(r: random.Random, lo=0, hi=600) -> tuple:
    q = r.choice([1, 1, 0.5, 0.125, 0.1])
    return (round(r.uniform(lo, hi) / q) * q, round(r.uniform(lo, hi) / q) * q,
            max(q, round(r.uniform(20, 160) / q) * q), max(q, round(r.uniform(20, 120) / q) * q))


def random_scenarios(n: int) -> list[tuple[tuple, dict]]:
    r = random.Random(SEED)
    out = []
    for _ in range(n):
        src, dst = rand_box(r), rand_box(r)
        obstacles = [rand_box(r) for _ in range(r.randint(0, 8))]
        if r.random() < 0.5:
            obstacles += [src, dst]
        kw: dict = {"margin": r.choice([14.0, 14.0, 7.0, 10.5, 5.25])}
        if r.random() < 0.3:
            kw["sides"] = (r.choice([None, *SIDES]), r.choice([None, *SIDES]))
        if r.random() < 0.4:
            kw["busy"] = {src: set(r.sample(SIDES, r.randint(0, 3))), dst: set(r.sample(SIDES, r.randint(0, 3)))}
        if r.random() < 0.3:
            kw["guides"] = [(r.uniform(-50, 700), r.uniform(-50, 700)) for _ in range(r.randint(0, 6))]
        if r.random() < 0.3:
            kw["fracs"] = (r.choice([None, 0.2, 0.3, 0.75, 1 / 3]), r.choice([None, 0.25, 0.8]))
        if r.random() < 0.5:
            drawn = []
            for _ in range(r.randint(0, 6)):
                a = (r.uniform(0, 700), r.uniform(0, 700))
                drawn.append((a, (a[0], r.uniform(0, 700))) if r.random() < 0.5 else (a, (r.uniform(0, 700), a[1])))
            if r.random() < 0.2:  # a few diagonals
                drawn.append(((r.uniform(0, 700), r.uniform(0, 700)), (r.uniform(0, 700), r.uniform(0, 700))))
            kw["penalty"] = engine_route.Crossings(r.choice([120.0, 1000.0, 0.5, 120]), drawn)
        out.append(((src, dst, obstacles), kw))
    return out


def run(calls: list[tuple[tuple, dict]], rust: bool) -> list[list]:
    pyroute._CORE = core if rust else None
    return [pyroute.route(*a, **kw) for a, kw in calls]


def clock(fn, reps=3) -> float:
    best = float("inf")
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t)
    return best


def compare(name: str, calls: list[tuple[tuple, dict]]) -> bool:
    py, rs = run(calls, False), run(calls, True)
    same = sum(a == b for a, b in zip(py, rs))
    print(f"{name}: {same} of {len(calls)} identical")
    for k, (a, b) in enumerate(zip(py, rs)):
        if a != b:
            print(f"  first difference at #{k}:\n    python {a}\n    rust   {b}")
            break
    return same == len(calls)


if __name__ == "__main__":
    recorded = record_examples()
    print(f"recorded {len(recorded)} route() calls from the examples")
    ok = compare("recorded calls", recorded)
    ok &= compare("random scenarios", random_scenarios(RANDOM_SCENARIOS))
    t_py = clock(lambda: run(recorded, False))
    t_rs = clock(lambda: run(recorded, True))
    print("\n## Routing time over the recorded calls (best of 3, warm)\n")
    print("| Work | Python | Rust via PyO3 | Speed-up |\n|---|---|---|---|")
    print(f"| route() x {len(recorded)} | {t_py * 1e3:.0f} ms | {t_rs * 1e3:.1f} ms | {t_py / t_rs:.1f}x |")
    sys.exit(0 if ok else 1)
