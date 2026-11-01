"""The Rust core (``spinagram._core``, compiled from ``rust/``), spinagram's main implementation.

The extension ships in every spinagram wheel, so the core is on by default. ``SPINAGRAM_RUST=0`` switches every
ported function back to the pure-Python implementation, which stays as the reference the parity checks compare
against.
"""
from __future__ import annotations

import functools
import importlib
import os
import warnings
from types import ModuleType


@functools.cache
def _load() -> ModuleType | None:
    try:
        return importlib.import_module("spinagram._core")
    except ImportError as exc:
        warnings.warn(f"the Rust core spinagram._core is not importable ({exc}); using the pure-Python engine",
                      stacklevel=3)
        return None


def core() -> ModuleType | None:
    if os.environ.get("SPINAGRAM_RUST", "1") in ("", "0"):
        return None
    return _load()


def font_args(font) -> tuple[str | None, float, int]:
    """A FontRef as the core takes it: (file, size, weight)."""
    return (str(font.file) if font.file is not None else None, font.size, font.weight)
