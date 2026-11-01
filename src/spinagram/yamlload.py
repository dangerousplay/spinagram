"""Fast YAML loading: libyaml's C parser when available, and a per-file parse cache.

``parse`` gives the data ``yaml.safe_load`` gives (same YAML 1.1 semantics). ``load_file`` caches the parsed
file on (absolute path, ``st_mtime_ns``, ``st_size``) so themes and icon registries are parsed once per
process, and hands every caller its own deep copy so nobody can mutate the cache.
"""
from __future__ import annotations

import copy
import os
import threading
from pathlib import Path
from typing import Any

import yaml

_cache: dict[str, tuple[tuple[int, int], Any]] = {}
_lock = threading.Lock()


def _loader() -> type:
    return yaml.CSafeLoader if yaml.__with_libyaml__ else yaml.SafeLoader


def parse(text: str) -> Any:
    """Parse YAML text like ``yaml.safe_load``, with libyaml when present."""
    return yaml.load(text, Loader=_loader())  # noqa: S506 - a safe loader


def stat_key(path: Path) -> tuple[int, int] | None:
    """``(st_mtime_ns, st_size)`` of ``path``, or None when it does not exist."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size


def load_file(path: Path | str) -> Any:
    """Parse a YAML file, reusing the parse while the file is unchanged. Raises ``FileNotFoundError``."""
    p = Path(path)
    key = stat_key(p)
    if key is None:
        raise FileNotFoundError(str(p))
    name = os.path.abspath(p)
    with _lock:
        hit = _cache.get(name)
        if hit is not None and hit[0] == key:
            return copy.deepcopy(hit[1])
        data = parse(p.read_text(encoding="utf-8"))
        _cache[name] = (key, data)
        return copy.deepcopy(data)
