"""Every scene the examples build (the same targets as ``rust/bench/render_all.sh``), cached per process."""
import os
from functools import lru_cache
from pathlib import Path

from spinagram import api, cli
from spinagram.theme import Theme

ROOT = Path(__file__).resolve().parents[1]


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


@lru_cache(maxsize=None)
def example_scenes() -> tuple:
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        return tuple(sc for t in targets() for sc in api.scenes(cli._collect([t], None), Theme.load(None)))
    finally:
        os.chdir(cwd)


@lru_cache(maxsize=None)
def example_diagrams() -> tuple:
    """Every diagram of the examples (the same targets as ``example_scenes``)."""
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        return tuple(d for t in targets() for d in cli._collect([t], None))
    finally:
        os.chdir(cwd)
