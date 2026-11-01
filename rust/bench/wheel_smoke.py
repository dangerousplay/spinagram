"""Check an installed spinagram wheel (or source build) on this platform.

Imports the core, renders examples to SVG with and without it and requires byte-identical files, then renders a
PNG through resvg. Exits 1 on any failure. Run from the repository root with spinagram installed in the current
interpreter:

    python rust/bench/wheel_smoke.py
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

EXAMPLES = ["examples/decision.yaml", "examples/software_architecture.yaml", "examples/styling/"]


def render(out: Path, rust: bool, formats: str) -> None:
    env = {**os.environ, "SPINAGRAM_RUST": "1" if rust else "0"}
    cmd = [sys.executable, "-m", "spinagram", "render", *EXAMPLES, "-f", formats, "--no-gallery", "-o", str(out)]
    subprocess.run(cmd, env=env, check=True, stdout=subprocess.DEVNULL)


def main() -> int:
    from importlib.metadata import version

    from spinagram import _core  # noqa: F401  an ImportError here is the failure this script exists to catch

    print(f"spinagram {version('spinagram')} with spinagram._core on {platform.system()} {platform.machine()}")
    os.environ["SPINAGRAM_RUST"] = "1"
    from spinagram import rust

    if rust.core() is None:
        print("SPINAGRAM_RUST=1 but spinagram.rust.core() is None")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        py, rs = Path(tmp, "py"), Path(tmp, "rs")
        render(py, rust=False, formats="svg")
        render(rs, rust=True, formats="svg,png")
        svgs = sorted(p.relative_to(py) for p in py.rglob("*.svg"))
        differ = [str(p) for p in svgs if (py / p).read_bytes() != (rs / p).read_bytes()]
        pngs = list(rs.rglob("*.png"))
        print(f"{len(svgs) - len(differ)}/{len(svgs)} SVGs identical, {len(pngs)} PNGs")
        if not svgs or differ or len(pngs) != len(svgs):
            for name in differ:
                print(f"differs: {name}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
