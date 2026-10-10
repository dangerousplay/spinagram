"""Icon packs for the UI: registry state, icon listings, file lookup and background fetch jobs."""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from .. import icons


class FetchConflict(Exception):
    """A fetch of this pack is already running."""


class Offline(Exception):
    """``DIAGRAMKIT_OFFLINE=1``: downloads are disabled."""


class PackService:
    def __init__(self, publish: Callable[[dict], None] | None = None, cwd: Path | None = None):
        self.publish = publish or (lambda e: None)
        self.cwd = cwd
        self._jobs: dict[str, str | None] = {}  # pack → None while running, error text when it failed
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(2, thread_name_prefix="dk-fetch")

    def registry(self) -> dict[str, icons.Pack]:
        return icons.registry(self.cwd)

    def registry_files(self) -> list[Path]:
        return [icons.user_registry(), (self.cwd or Path.cwd()) / icons.PROJECT_REGISTRY]

    @staticmethod
    def offline() -> bool:
        return os.environ.get("DIAGRAMKIT_OFFLINE") == "1"

    def _pack(self, name: str) -> icons.Pack:
        pack = self.registry().get(name)
        if pack is None:
            raise KeyError(name)
        return pack

    def _index(self, pack: icons.Pack) -> dict | None:
        f = pack.dir / "index.json"
        if not f.exists():
            return None
        return icons.index(pack, auto_fetch=False)

    def list(self) -> list[dict]:
        out = []
        for name, p in sorted(self.registry().items()):
            idx = None
            err = None
            try:
                idx = self._index(p)
            except Exception as exc:  # noqa: BLE001 — a corrupt cache shows as an error, not a crash
                err = str(exc)
            with self._lock:
                running = name in self._jobs and self._jobs[name] is None
                err = err or (self._jobs.get(name) if not running else None)
            out.append({"name": name, "title": p.title, "version": p.version, "origin": p.origin,
                        "license": p.license, "homepage": p.homepage, "source": p.source.get("type"),
                        "fetched": idx is not None, "count": len(idx["icons"]) if idx else 0,
                        "fetching": running, "error": err})
        return out

    def icons(self, name: str) -> list[dict]:
        idx = self._index(self._pack(name))
        if idx is None:
            raise LookupError(f"pack {name!r} is not downloaded")
        by_target: dict[str, list[str]] = {}
        for alias, target in idx["aliases"].items():
            by_target.setdefault(target, []).append(alias)
        return [{"name": n, "aliases": sorted(by_target.get(n, [])),
                 "tones": [t for t in ("light", "dark") if e.get(t)],
                 "ext": Path(e.get("light") or e.get("dark") or "").suffix.lstrip(".")}
                for n, e in idx["icons"].items()]

    def icon_file(self, name: str, icon: str, tone: str = "light") -> Path:
        pack = self._pack(name)
        idx = self._index(pack)
        entry = (idx or {}).get("icons", {}).get(icon)
        if not entry:
            raise KeyError(icon)
        fname = entry.get(tone) or entry.get("light") or entry.get("dark")
        f = (pack.dir / fname).resolve()
        if not fname or f.parent != pack.dir.resolve() or not f.is_file():
            raise KeyError(icon)
        return f

    # fetch ----------------------------------------------------------------------------------------
    def start_fetch(self, name: str) -> None:
        pack = self._pack(name)
        if self.offline():
            raise Offline("DIAGRAMKIT_OFFLINE=1")
        with self._lock:
            if name in self._jobs and self._jobs[name] is None:
                raise FetchConflict(name)
            self._jobs[name] = None
        self.publish({"type": "pack", "name": name, "status": "fetching"})
        self._pool.submit(self._run, pack)

    def _run(self, pack: icons.Pack) -> None:
        try:
            icons.fetch(pack, force=True)
            icons._INDEX_CACHE.pop(f"{pack.name}@{pack.version}", None)
            with self._lock:
                self._jobs.pop(pack.name, None)
            self.publish({"type": "pack", "name": pack.name, "status": "done"})
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._jobs[pack.name] = str(exc) or type(exc).__name__
            self.publish({"type": "pack", "name": pack.name, "status": "failed", "error": self._jobs[pack.name]})

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
