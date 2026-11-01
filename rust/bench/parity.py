"""Spike harness: compare spinagram_core (Rust) with spinagram.text / engine.textfit (Python, Pillow).

Run from the repo root after installing the wheel:
    uv run --all-extras --no-sync python rust/bench/parity.py
"""
from __future__ import annotations

import re
import statistics
import time
from pathlib import Path

import spinagram_core as core
from spinagram.engine import textfit
from spinagram.text import BUNDLED, measure
from spinagram.theme import FontRef

ROOT = Path(__file__).resolve().parents[2]
SYSTEM = Path("/System/Library/Fonts/Supplemental")
FONT_FILES = [p for _, p in BUNDLED] + [SYSTEM / n for n in (
    "Arial.ttf", "Arial Bold.ttf", "Verdana.ttf", "Georgia.ttf", "Times New Roman.ttf", "Courier New.ttf",
    "Trebuchet MS.ttf", "Tahoma.ttf")]
FONT_FILES = [p for p in FONT_FILES if p.exists()]
SIZES = [9, 10, 11, 12, 13, 13.5, 14, 15, 16, 18, 20, 22, 24, 28, 32]
FALLBACKS = [str(p) for _, p in BUNDLED]


def corpus() -> list[str]:
    """Every quoted string in the examples (titles, bodies, labels), plus edge cases."""
    found: set[str] = set()
    for f in (ROOT / "examples").rglob("*.py"):
        found.update(re.findall(r'"([^"\n]{1,120})"', f.read_text()))
    for f in (ROOT / "examples").rglob("*.yaml"):
        found.update(re.findall(r":\s*([A-Za-z][^\n#]{1,100})", f.read_text()))
    found.update(["10.0.0.0/16-subnet-a", "api.example.com/v1/orders", "→ ✓ ★ ∑ √ ⚙", "Ünïcödé façade naïve",
                  "WAVE AVATAR Typography", "x", "  spaced   out  "])
    return sorted(s for s in found if s.strip())


def fontref(path: Path | None, size: float, weight: int = 400) -> FontRef:
    return FontRef("t", weight, size=size, file=path)


def rust_font(path: Path | None, size: float, weight: int = 400):
    return (str(path) if path else None, size, weight)


def parity_measure(texts: list[str]) -> None:
    rows = []
    for path in FONT_FILES:
        diffs = [abs(measure(t, fontref(path, s)) - core.measure(t, rust_font(path, s), FALLBACKS))
                 for t in texts for s in SIZES]
        rows.append((path.name, len(diffs), sum(d < 1e-9 for d in diffs) / len(diffs), max(diffs),
                     statistics.mean(diffs)))
    est = [abs(measure(t, fontref(None, s, w)) - core.measure(t, rust_font(None, s, w), FALLBACKS))
           for t in texts for s in SIZES for w in (400, 700)]
    rows.append(("(no file: estimate)", len(est), sum(d < 1e-9 for d in est) / len(est), max(est), statistics.mean(est)))
    print("\n## measure(): Rust vs Pillow\n")
    print("| Font | Samples | Exact | Max diff px | Mean diff px |\n|---|---|---|---|---|")
    for name, n, exact, mx, mean in rows:
        print(f"| {name} | {n} | {exact:.1%} | {mx:.3f} | {mean:.4f} |")


def specs_for(texts: list[str], path: Path | None):
    for i in range(0, len(texts) - 1, 2):
        title, body = texts[i], texts[i + 1]
        yield [textfit.BlockSpec([title], fontref(path, 18, 700), 1.25, "#000"),
               textfit.BlockSpec([body], fontref(path, 13), 1.35, "#333")]


def fit_python(specs, w, h, mode):
    r = textfit.fit_blocks(specs, w, h, mode)
    return [(b.lines, b.font.size) for b in r.blocks], r.strategy, r.ok


def fit_rust(specs, w, h, mode):
    rs = [(sp.paragraphs, rust_font(sp.font.file, sp.font.size, sp.font.weight), sp.leading) for sp in specs]
    blocks, _, strategy, ok, _ = core.fit_blocks(rs, w, h, mode, textfit.MIN_SCALE, textfit.BREAK_ON, 10, FALLBACKS)
    return [(lines, size) for lines, size, _ in blocks], strategy, ok


BOXES = [(120, 60), (160, 84), (210, 84), (260, 120)]
MODES = ["none", "shrink", "grow", "shrink-then-grow"]


def parity_fit(texts: list[str]) -> list[tuple]:
    cases = [(specs, w, h, mode) for path in [None, *FONT_FILES[2:5]] for specs in specs_for(texts, path)
             for w, h in BOXES for mode in MODES]
    same = sum(fit_python(*c) == fit_rust(*c) for c in cases)
    print("\n## fit_blocks(): same lines, sizes, strategy and ok\n")
    print(f"{same} of {len(cases)} cases ({same / len(cases):.2%})")
    return cases


def bench(texts: list[str], cases: list[tuple]) -> None:
    def clock(fn, reps=3):
        best = float("inf")
        for _ in range(reps):
            t = time.perf_counter()
            fn()
            best = min(best, time.perf_counter() - t)
        return best

    arial = FONT_FILES[2]
    m_py = clock(lambda: [measure(t, fontref(arial, 14)) for t in texts])
    m_rs = clock(lambda: [core.measure(t, rust_font(arial, 14), FALLBACKS) for t in texts])
    f_py = clock(lambda: [fit_python(*c) for c in cases])
    f_rs = clock(lambda: [fit_rust(*c) for c in cases])
    print("\n## Speed (best of 3, warm caches)\n")
    print("| Work | Python | Rust via PyO3 | Speed-up |\n|---|---|---|---|")
    print(f"| measure() x {len(texts)} strings | {m_py * 1e3:.1f} ms | {m_rs * 1e3:.1f} ms | {m_py / m_rs:.1f}x |")
    print(f"| fit_blocks() x {len(cases)} boxes | {f_py * 1e3:.0f} ms | {f_rs * 1e3:.0f} ms | {f_py / f_rs:.1f}x |")


if __name__ == "__main__":
    texts = corpus()
    print(f"corpus: {len(texts)} strings, {len(FONT_FILES)} font files, {len(SIZES)} sizes")
    parity_measure(texts)
    cases = parity_fit(texts)
    bench(texts, cases)
