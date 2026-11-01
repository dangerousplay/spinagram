"""SVG and PNG parity and speed: the Rust core against the Python writer and Chromium.

SVG: every example scene is written by the Python writer and by the Rust core in each font mode; the bytes must be
identical. PNG (unless --svg-only, and only when Chromium is available): resvg against Chromium at scale 1 per
example: mean absolute channel difference <= 8 and at most 2 % of pixels with a channel difference > 64.
Exits 1 on any SVG difference or similarity breach. Run from anywhere after installing the wheel:
    uv run --all-extras --no-sync python rust/bench/svg_png_parity.py [--svg-only]
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

from spinagram import _core as core
from PIL import Image, ImageChops, ImageStat

from spinagram import api, cli
from spinagram.backends import png, svg
from spinagram.theme import Theme

ROOT = Path(__file__).resolve().parents[2]
MEAN_LIMIT = 8.0
SHARE_LIMIT = 0.02
BIG = 64


def targets() -> list[str]:
    """Example folders (nested ones too), top-level example files and docs/diagrams."""
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


def example_scenes() -> list:
    os.chdir(ROOT)
    return [sc for t in targets() for sc in api.scenes(cli._collect([t], None), Theme.load(None))]


def clock(fn, reps=3) -> float:
    best = float("inf")
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t)
    return best


def write(scenes, fonts: str, rust: bool) -> list[str]:
    svg._CORE = core if rust else None
    return [svg.to_svg(sc, fonts) for sc in scenes]


def compare_svg(scenes) -> bool:
    ok = True
    for fonts in svg.FONT_MODES:
        py, rs = write(scenes, fonts, False), write(scenes, fonts, True)
        same = sum(a == b for a, b in zip(py, rs))
        print(f"svg fonts={fonts}: {same} of {len(scenes)} identical")
        for sc, a, b in zip(scenes, py, rs):
            if a != b:
                at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                print(f"  first difference in {sc.slug} at byte {at}:\n    python {a[max(0, at - 40):at + 60]!r}\n"
                      f"    rust   {b[max(0, at - 40):at + 60]!r}")
                break
        ok &= same == len(scenes)
    return ok


def similarity(a: Path, b: Path) -> tuple[float, float] | None:
    """(mean absolute channel difference, share of pixels with a channel difference > 64), or None on a size mismatch."""
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if ia.size != ib.size:
        return None
    diff = ImageChops.difference(ia, ib)
    mean = sum(ImageStat.Stat(diff).mean) / 3
    big = ImageChops.lighter(*[band.point(lambda v: 255 if v > BIG else 0) for band in diff.split()][:2])
    big = ImageChops.lighter(big, diff.split()[2].point(lambda v: 255 if v > BIG else 0))
    share = sum(big.histogram()[1:]) / (ia.size[0] * ia.size[1])
    return mean, share


def chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch().close()
        return True
    except Exception:  # noqa: BLE001 - not installed, or no browser downloaded
        return False


def compare_png(scenes) -> tuple[bool, float, float]:
    png._CORE = core
    svg._CORE = core
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "chromium", Path(tmp) / "resvg"
        t = time.perf_counter()
        chrome = png.PngBackend(scale=1)._render_chromium(scenes, a)
        t_chrome = time.perf_counter() - t
        t = time.perf_counter()
        resvg = png.PngBackend(scale=1)._render_resvg(scenes, b)
        t_resvg = time.perf_counter() - t
        ok, worst_mean, worst_share = True, 0.0, 0.0
        for sc, pa, pb in zip(scenes, chrome, resvg):
            got = similarity(pa, pb)
            if got is None:
                print(f"  {sc.slug}: PNG sizes differ ({Image.open(pa).size} vs {Image.open(pb).size})")
                ok = False
                continue
            mean, share = got
            worst_mean, worst_share = max(worst_mean, mean), max(worst_share, share)
            if mean > MEAN_LIMIT or share > SHARE_LIMIT:
                print(f"  {sc.slug}: mean {mean:.2f} (limit {MEAN_LIMIT}), >64 share {share:.2%} (limit {SHARE_LIMIT:.0%})")
                ok = False
    print(f"png similarity over {len(scenes)} scenes: worst mean {worst_mean:.2f} (<= {MEAN_LIMIT}), "
          f"worst >64 share {worst_share:.2%} (<= {SHARE_LIMIT:.0%}): {'ok' if ok else 'BREACH'}")
    return ok, t_chrome, t_resvg


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg-only", action="store_true", help="skip the PNG comparison (CI has no Chromium)")
    args = ap.parse_args()
    scenes = example_scenes()
    print(f"{len(scenes)} example scenes")
    ok = compare_svg(scenes)
    t_py = clock(lambda: write(scenes, "subset", False))
    t_rs = clock(lambda: write(scenes, "subset", True))
    rows = [("svg writer (subset), all scenes", f"{t_py * 1e3:.0f} ms", f"{t_rs * 1e3:.0f} ms", f"{t_py / t_rs:.1f}x")]
    if not args.svg_only:
        if chromium_available():
            png_ok, t_chrome, t_resvg = compare_png(scenes)
            ok &= png_ok
            rows.append(("png at scale 1, all scenes (Chromium vs resvg)", f"{t_chrome * 1e3:.0f} ms",
                         f"{t_resvg * 1e3:.0f} ms", f"{t_chrome / t_resvg:.1f}x"))
        else:
            print("png similarity: skipped (Chromium is not available)")
    print("\n## Time (SVG best of 3, warm; PNG one run including Chromium start-up)\n")
    print("| Work | Python / Chromium | Rust | Speed-up |\n|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(r) + " |")
    sys.exit(0 if ok else 1)
