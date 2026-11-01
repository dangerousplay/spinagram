"""The optional Rust core (the ``spinagram-core`` wheel built from ``rust/``), ported a slice at a time.

Opt in with ``SPINAGRAM_RUST=1`` while the port is a spike. Without the wheel, or without the flag, every
function stays pure Python, so results never depend on whether Rust is installed.
"""
from __future__ import annotations

import os
from types import ModuleType


def core() -> ModuleType | None:
    if os.environ.get("SPINAGRAM_RUST", "0") in ("", "0"):
        return None
    try:
        import spinagram_core
    except ImportError:
        return None
    return spinagram_core


def font_args(font) -> tuple[str | None, float, int]:
    """A FontRef as the core takes it: (file, size, weight)."""
    return (str(font.file) if font.file is not None else None, font.size, font.weight)
