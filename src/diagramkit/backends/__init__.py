"""Backend protocol and registry.

A backend turns resolved scenes into files. Third-party backends register through the
``diagramkit.backends`` entry-point group; built-ins are always available.
"""
from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path
from typing import Protocol, Sequence

from ..scene import Scene

_BUILTIN = {
    "svg": "diagramkit.backends.svg:SvgBackend",
    "png": "diagramkit.backends.png:PngBackend",
    "pptx": "diagramkit.backends.pptx:PptxBackend",
    "figma": "diagramkit.backends.figma:FigmaBackend",
    "figjam": "diagramkit.backends.figma:FigjamBackend",
}


class Backend(Protocol):
    name: str

    def render(self, scenes: Sequence[Scene], out_dir: Path) -> list[Path]:
        """Write output files for ``scenes`` into ``out_dir``; return the paths written."""
        ...


def _load(target: str):
    mod, _, attr = target.partition(":")
    return getattr(import_module(mod), attr)


def available() -> dict[str, str]:
    found = dict(_BUILTIN)
    for ep in entry_points(group="diagramkit.backends"):
        found.setdefault(ep.name, ep.value)
    return found


def get_backend(name: str, **options) -> Backend:
    reg = available()
    if name not in reg:
        raise KeyError(f"unknown backend {name!r}; available: {', '.join(sorted(reg))}")
    return _load(reg[name])(**options)
