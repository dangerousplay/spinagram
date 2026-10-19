"""Backend protocol and registry.

A backend turns resolved scenes into files. Third-party backends register through the
``spinagram.backends`` entry-point group; built-ins are always available.
"""
from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path
from typing import Protocol, Sequence

from ..scene import Scene

_BUILTIN = {
    "svg": "spinagram.backends.svg:SvgBackend",
    "png": "spinagram.backends.png:PngBackend",
    "pptx": "spinagram.backends.pptx:PptxBackend",
    "figma": "spinagram.backends.figma:FigmaBackend",
    "figjam": "spinagram.backends.figma:FigjamBackend",
    "excalidraw": "spinagram.backends.excalidraw:ExcalidrawBackend",
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
    for ep in entry_points(group="spinagram.backends"):
        found.setdefault(ep.name, ep.value)
    return found


def get_backend(name: str, **options) -> Backend:
    reg = available()
    if name not in reg:
        raise KeyError(f"unknown backend {name!r}; available: {', '.join(sorted(reg))}")
    return _load(reg[name])(**options)
