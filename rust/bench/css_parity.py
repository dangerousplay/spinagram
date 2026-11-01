"""CSS parity and speed: matching and cascade in the Rust core against the Python implementation.

Compares `css.inspect()` (values, warnings, trace, unused selectors) across modes for every example and for seeded
random (diagram, stylesheet) pairs that use every selector feature and every `var()` form, then times the cascade
on a synthetic 500-node, 200-rule diagram. Exits 1 on any difference. Run from anywhere after installing the wheel:
    uv run --all-extras --no-sync python rust/bench/css_parity.py
"""
from __future__ import annotations

import os
import random
import sys
import time
from contextlib import ExitStack
from pathlib import Path

from spinagram import _core as core

from spinagram import Diagram, cli, css
from spinagram.theme import Theme

ROOT = Path(__file__).resolve().parents[2]
PAIRS = 1200
SEED = 20241101
THEME = Theme.load(None)
KINDS = ["box", "decision", "note"]
CLASSES = ["hot", "cold", "a", "b", "wide"]
COLOURS = ["#112233", "red", "#abc", "rgb(10, 20, 30)", "teal", "#12345678"]
SAFE = False  # the benchmark stylesheet must not raise: colours always resolve
PROPS = ["fill", "stroke", "color", "stroke-width", "opacity", "font-size", "font-family", "font-weight", "border-radius",
         "box-shadow", "marker-end", "stroke-dasharray", "frobnicate"]


def targets() -> list[str]:
    out = []
    for p in sorted((ROOT / "examples").iterdir()):
        if p.suffix in (".py", ".yaml"):
            out.append(f"examples/{p.name}")
        elif p.is_dir():
            out.append(f"examples/{p.name}/")
    nested = sorted(f"{d.relative_to(ROOT)}/" for d in (ROOT / "examples").rglob("*")
                    if d.is_dir() and d.parent != ROOT / "examples" and "__pycache__" not in d.parts
                    and any(f.suffix in (".py", ".yaml") for f in d.iterdir()))
    return out + nested + ["docs/diagrams/"]


def example_diagrams() -> list:
    os.chdir(ROOT)
    return [d for t in targets() for d in cli._collect([t], None)]


def outcome(d, use_core: bool):
    css._CORE = core if use_core else None
    try:
        return "ok", css.inspect(d, THEME), css.styles(d, THEME)
    except css.CssValueError as exc:
        return "error", str(exc)


# random diagrams ----------------------------------------------------------------------------------
def random_diagram(r: random.Random, n: int) -> tuple[Diagram, list[str]]:
    d = Diagram(f"R{n}", "random")
    ids: list[str] = []
    counter = [0]

    def inline() -> str | None:
        return random_decls(r, 2, custom=False) if r.random() < 0.15 else None

    def make_node(depth_ids):
        counter[0] += 1
        nid = f"n{counter[0]}"
        kind = r.choice(KINDS)
        d.add(kind, f"Title {nid}", id=nid, cls=" ".join(r.sample(CLASSES, r.randint(0, 2))) or None, css=inline())
        ids.append(nid)

    def fill(stack: ExitStack, depth: int) -> None:
        for _ in range(r.randint(1, 4)):
            if depth < 2 and r.random() < 0.3:
                counter[0] += 1
                gid = f"g{counter[0]}"
                with d.group(f"Group {gid}", id=gid, cls=" ".join(r.sample(CLASSES, r.randint(0, 2))) or None,
                             css=inline()):
                    fill(stack, depth + 1)
            else:
                make_node(ids)

    with ExitStack() as stack:
        fill(stack, 0)
    for _ in range(r.randint(0, 4)):
        if len(ids) > 1:
            a, b = r.sample(ids, 2)
            d.edge(a, b, cls=" ".join(r.sample(CLASSES, r.randint(0, 2))) or None, css=inline())
    return d, ids


def random_value(r: random.Random, prop: str, custom_names: list[str]) -> str:
    if r.random() < 0.3 and custom_names:  # a var() form
        name = r.choice(custom_names)
        colour = prop in ("fill", "stroke", "color", "box-shadow")
        safe = [f"var({name}, {random_plain(r, prop)})", f"var(--nope, {random_plain(r, prop)})",
                f"var( {name} , {random_plain(r, prop)} )"]
        risky = [f"var({name})", f"var({name},)", f"var( {name} )", "var(--missing)", f"var(var({name}))"]
        return r.choice(safe if (SAFE or colour and r.random() < 0.8) else safe + risky)
    return random_plain(r, prop)


def random_plain(r: random.Random, prop: str) -> str:
    if prop in ("fill", "stroke", "color"):
        return r.choice(COLOURS + ["none"])
    if prop in ("stroke-width", "border-radius", "font-size"):
        return r.choice(["1", "2.5", "12px", "0", "-3", "abc"])
    if prop == "opacity":
        return r.choice(["0.5", "50%", "1", "2", "x"])
    if prop == "font-weight":
        return r.choice(["bold", "400", "700", "heavy"])
    if prop == "font-family":
        return r.choice(["Inter", "'Fira Code'", "serif"])
    if prop == "box-shadow":
        return r.choice(["none", "2px 2px 4px #00000040", "0 0 3px red"])
    if prop == "marker-end":
        return r.choice(["arrow", "bar", "none", "star"])
    if prop == "stroke-dasharray":
        return r.choice(["4 2", "none", "5,3"])
    return "1"


def random_decls(r: random.Random, count: int, custom: bool = True) -> str:
    names = [f"--{c}" for c in ("x", "y", "z")]
    out = []
    for _ in range(r.randint(1, count)):
        if custom and r.random() < 0.3:
            name = r.choice(names)
            out.append(f"{name}: {random_value(r, 'fill', [n for n in names if n != name])}"
                       + (" !important" if r.random() < 0.1 else ""))
        else:
            prop = r.choice(PROPS)
            out.append(f"{prop}: {random_value(r, prop, names)}" + (" !important" if r.random() < 0.2 else ""))
    return "; ".join(out)


def random_compound(r: random.Random, ids: list[str]) -> str:
    parts = []
    if r.random() < 0.5:
        parts.append(r.choice(["node", "edge", "group", "diagram", "box", "decision", "note", "chip", "*"]))
    if r.random() < 0.35:
        parts.append("." + r.choice(CLASSES))
    if r.random() < 0.15 and ids:
        parts.append("#" + r.choice(ids))
    if r.random() < 0.2:
        parts.append(r.choice(["[kind]", "[kind=box]", "[kind=decision]", '[label="Title n1"]', "[icon]", "[from]",
                               "[label='x']"]))
    if r.random() < 0.2:
        parts.append(r.choice([":first-child", ":last-child", ":root"]))
    if r.random() < 0.15:
        inner = ", ".join(r.choice([".hot", "node", "#n1", ":first-child", "group node"]) for _ in range(r.randint(1, 2)))
        parts.append(f":not({inner})")
    return "".join(parts) or "*"


def random_selector(r: random.Random, ids: list[str]) -> str:
    sel = random_compound(r, ids)
    for _ in range(r.choice([0, 0, 1, 2])):
        sel = f"{sel}{r.choice([' ', ' > ', '>'])}{random_compound(r, ids)}"
    if r.random() < 0.2:
        sel += r.choice(["::title", "::body", "::label"])
    return sel


def random_sheet(r: random.Random, ids: list[str]) -> str:
    rules = []
    for _ in range(r.randint(2, 12)):
        sels = ", ".join(random_selector(r, ids) for _ in range(r.choice([1, 1, 2])))
        rules.append(f"{sels} {{ {random_decls(r, 4)} }}")
    if r.random() < 0.1:
        rules.append("> node { fill: red }")  # a selector the core cannot parse: the Python path runs
    return "\n".join(rules)


def compare_examples() -> bool:
    diagrams = example_diagrams()
    same = sum(outcome(d, False) == outcome(d, True) for d in diagrams)
    print(f"examples: {same} of {len(diagrams)} identical (inspect and styles)")
    return same == len(diagrams)


def compare_random() -> bool:
    r = random.Random(SEED)
    same, errors, used = 0, 0, 0
    first = None
    for n in range(PAIRS):
        d, ids = random_diagram(r, n)
        d.css = random_sheet(r, ids)
        a, b = outcome(d, False), outcome(d, True)
        errors += a[0] == "error"
        used += a[0] == "ok" and bool(a[1]["styled"])
        if a == b:
            same += 1
        elif first is None:
            first = (n, d.css, a, b)
    print(f"random pairs: {same} of {PAIRS} identical ({used} styled and valid, {errors} raise CssValueError)")
    if first:
        n, sheet, a, b = first
        print(f"  first difference at pair {n}:\n{sheet}\n  python {str(a)[:300]}\n  rust   {str(b)[:300]}")
    return same == PAIRS


# benchmark ----------------------------------------------------------------------------------------
def benchmark_diagram() -> Diagram:
    r = random.Random(7)
    global SAFE
    SAFE = True
    d = Diagram("BENCH", "benchmark")
    ids: list[str] = []
    for g in range(20):
        with d.group(f"G{g}", id=f"grp{g}", cls=r.choice(CLASSES)):
            for k in range(25):
                nid = f"n{g}-{k}"
                d.add(r.choice(KINDS), nid, id=nid, cls=" ".join(r.sample(CLASSES, r.randint(0, 2))) or None)
                ids.append(nid)
    for _ in range(40):
        a, b = r.sample(ids, 2)
        d.edge(a, b, cls=r.choice(CLASSES))
    rules = []
    for _ in range(200):
        rules.append(f"{random_selector(r, ids[:50])} {{ {random_decls(r, 3)} }}")
    d.css = "\n".join(rules)
    SAFE = False
    return d


def clock(fn, reps=3) -> float:
    best = float("inf")
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t)
    return best


def python_cascade(root, rules) -> None:
    """Matching and ordering only: what `compute` asks the core for (the Python side of `declared`)."""
    for el in css._walk(root):
        for pseudo in (None, "title", "body", "label"):
            found = []
            for rule in rules:
                for sel in rule.selectors:
                    if sel.pseudo_element == pseudo and css.matches(sel, el):
                        for i, d in enumerate(rule.decls):
                            found.append(((2 if d.important else 0, sel.specificity, rule.order, i), d))
            if el.inline and pseudo is None:
                for i, d in enumerate(css._inline(el.inline)):
                    found.append(((3 if d.important else 1, (0, 0, 0), 0, i), d))
            found.sort(key=lambda f: f[0])


def timings() -> list[tuple[str, float, float]]:
    d = benchmark_diagram()
    rules = []
    for text, origin in css.sheets_for(d, THEME):
        rules += css.parse(text, origin, order_base=len(rules))[0]
    root, _ = css.tree(d)
    n_el = len(list(css._walk(root)))
    print(f"benchmark: {n_el} elements, {len(rules)} rules, {sum(len(r.selectors) for r in rules)} selectors")
    css._CORE = core
    t_cascade_rs = clock(lambda: css._rust_cascade(root, rules))
    t_cascade_py = clock(lambda: python_cascade(root, rules))

    def compute_in(mode):
        css._CORE = mode
        css.compute(root, rules, THEME, [])

    try:
        t_py = clock(lambda: compute_in(None))
        t_rs = clock(lambda: compute_in(core))
    except css.CssValueError:
        t_py = t_rs = float("nan")
    return [("matching + cascade (JSON build, core call)", t_cascade_py, t_cascade_rs), ("compute() end to end", t_py, t_rs)]


if __name__ == "__main__":
    ok = compare_examples()
    ok &= compare_random()
    rows = timings()
    print("\n## Time on the benchmark diagram (best of 3, warm)\n")
    print("| Work | Python | Rust via PyO3 | Speed-up |\n|---|---|---|---|")
    for name, py, rs in rows:
        print(f"| {name} | {py * 1e3:.0f} ms | {rs * 1e3:.1f} ms | {py / rs:.1f}x |")
    sys.exit(0 if ok else 1)
