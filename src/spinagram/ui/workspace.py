"""The specs a ``serve`` session watches: loading, rendering to SVG, caching and invalidation."""
from __future__ import annotations

import re
import sys
import threading
import traceback
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from ..autolayout import apply_layout
from ..backends.svg import to_svg
from ..layout import build_scene
from ..model import Diagram
from ..theme import Theme, _load_raw
from ..yaml_io import load

SPEC_EXTS = {".yaml", ".yml", ".py"}


def _missing_packs(messages: list[str]) -> list[str]:
    """Packs named in "icon 'pack:name' not found" warnings that are registered but not downloaded."""
    from .. import icons

    refs = {m.group(1) for msg in messages for m in [re.search(r"icon '([\w.-]+):", msg)] if m}
    if not refs:
        return []
    reg = icons.registry()
    return sorted(r for r in refs if r in reg and not (reg[r].dir / "index.json").exists())


class RenderError(Exception):
    def __init__(self, message: str, file: str | None = None):
        super().__init__(message)
        self.file = file


def _message(exc: BaseException) -> str:
    """Spec errors are already human-readable; anything else keeps its type and the last frame."""
    msg = str(exc) or type(exc).__name__
    if isinstance(exc, (ValueError, KeyError, FileNotFoundError)):
        return msg
    tb = traceback.extract_tb(exc.__traceback__)
    where = f" ({Path(tb[-1].filename).name}:{tb[-1].lineno})" if tb else ""
    return f"{type(exc).__name__}: {msg}{where}"


@dataclass
class SpecFile:
    path: Path
    rel: str
    diagrams: list[Diagram] = field(default_factory=list)
    error: str | None = None


class Workspace:
    """Spec files under ``paths`` rendered with one theme. Thread-safe (renders run in a pool)."""

    def __init__(self, paths: list[str | Path], theme: str | Path | None = None, layout: str | None = None):
        self.paths = [Path(p).expanduser().resolve() for p in (paths or ["."])]
        for p in self.paths:
            if not p.exists():
                raise FileNotFoundError(f"{p}: no such file or directory")
        self.theme_ref = theme
        self.layout = layout
        self.theme: Theme | None = None
        self.theme_error: str | None = None
        self.theme_gen = 0
        self.files: dict[str, SpecFile] = {}
        self._cache: dict[tuple, str] = {}
        self._lock = threading.RLock()
        self.reload_theme()
        self.rescan()

    # discovery ------------------------------------------------------------------------------------
    def _base(self, f: Path) -> Path:
        for p in self.paths:
            if p.is_dir() and f.is_relative_to(p):
                return p
        return f.parent

    def spec_dirs(self) -> set[Path]:
        return {p if p.is_dir() else p.parent for p in self.paths}

    def scan(self) -> list[Path]:
        found: list[Path] = []
        for p in self.paths:
            items = sorted(p.iterdir()) if p.is_dir() else [p]
            found += [f for f in items if f.is_file() and f.suffix in SPEC_EXTS and not f.name.startswith("_")]
        return found

    def rel(self, f: Path) -> str:
        base = self._base(f)
        return f.relative_to(base).as_posix() if len(self.paths) == 1 else f"{base.name}/{f.relative_to(base).as_posix()}"

    def rescan(self) -> bool:
        """Load new files, drop removed ones. True when the file set changed."""
        with self._lock:
            now = {self.rel(f): f for f in self.scan()}
            changed = set(now) != set(self.files)
            for rel in list(self.files):
                if rel not in now:
                    del self.files[rel]
            for rel, f in now.items():
                if rel not in self.files:
                    self.files[rel] = self._load(f, rel)
            return changed

    def _load(self, f: Path, rel: str) -> SpecFile:
        dont_write = sys.dont_write_bytecode
        if f.suffix == ".py":
            self._purge_modules(f.parent)
            # no .pyc for helpers: a quick edit keeping size and mtime-second would reuse stale bytecode
            sys.dont_write_bytecode = True
        try:
            return SpecFile(f, rel, load(f))
        except Exception as exc:  # noqa: BLE001 — any spec failure is shown in the UI, never fatal
            return SpecFile(f, rel, error=_message(exc))
        finally:
            sys.dont_write_bytecode = dont_write

    @staticmethod
    def _purge_modules(folder: Path) -> None:
        """Forget helper modules imported from a spec folder so a ``.py`` spec sees edited helpers."""
        folder = folder.resolve()
        local = {f.stem for f in folder.glob("*.py")}  # also a same-named module cached from elsewhere
        for name, mod in list(sys.modules.items()):
            fn = getattr(mod, "__file__", None)
            if name in local or (fn and Path(fn).resolve().parent == folder):
                del sys.modules[name]

    # theme ----------------------------------------------------------------------------------------
    def reload_theme(self) -> None:
        with self._lock:
            try:
                self.theme, self.theme_error = Theme.load(self.theme_ref), None
            except Exception as exc:  # noqa: BLE001
                self.theme, self.theme_error = None, _message(exc)
            self.theme_gen += 1
            self._cache.clear()

    def theme_roots(self) -> list[Path]:
        """Directories of the active theme and every theme it extends."""
        roots: list[Path] = []
        ref, rel = self.theme_ref, None
        import os

        ref = ref or os.environ.get("SPINAGRAM_THEME") or "default"
        while ref:
            try:
                raw = _load_raw(ref, rel)
            except Exception:  # noqa: BLE001
                break
            root = Path(raw["_root"])
            if root in roots:
                break
            roots.append(root)
            import yaml

            own = yaml.safe_load((root / "theme.yaml").read_text(encoding="utf-8")) or {}
            ref, rel = own.get("extends"), root
        return roots

    # changes --------------------------------------------------------------------------------------
    def reload_files(self, changed: list[Path]) -> list[str]:
        """Reload the spec files a change touches; returns the affected diagram keys."""
        with self._lock:
            targets: set[str] = set()
            for c in changed:
                c = c.resolve()
                for rel, sf in self.files.items():
                    if sf.path == c:
                        targets.add(rel)
                    elif sf.path.parent == c.parent and (c.name.startswith("_") or c.suffix == ".py"):
                        targets.add(rel)  # _defaults.yaml or a helper next to the spec
            keys: list[str] = []
            for rel in targets:
                old = self.files[rel]
                keys += [self.key(rel, d) for d in old.diagrams]
                self.files[rel] = new = self._load(old.path, rel)
                keys += [self.key(rel, d) for d in new.diagrams]
            self._cache = {k: v for k, v in self._cache.items() if k[0] not in keys}
            return sorted(set(keys))

    def all_keys(self) -> list[str]:
        return [self.key(rel, d) for rel, sf in self.files.items() for d in sf.diagrams]

    # rendering ------------------------------------------------------------------------------------
    @staticmethod
    def key(rel: str, d: Diagram) -> str:
        return f"{rel}#{d.id}"

    def find(self, key: str) -> tuple[SpecFile, Diagram | None]:
        rel, _, did = key.partition("#")
        sf = self.files.get(rel)
        if sf is None:
            raise KeyError(key)
        return sf, next((d for d in sf.diagrams if d.id == did), None)

    def render(self, key: str, layout: str | None = None) -> tuple[str, dict]:
        """SVG text and info of one diagram; raises ``RenderError`` with the reason.

        Info: ``overflow`` (layout bigger than the canvas), ``warnings`` (e.g. icons not found) and
        ``missing_packs`` (referenced icon packs that are not downloaded). Renders are serialised:
        warnings are captured per render, and layout engines spawn processes anyway."""
        with self._lock:
            sf, d = self.find(key)
            if sf.error:
                raise RenderError(sf.error, sf.rel)
            if d is None:
                raise KeyError(key)
            if self.theme is None:
                raise RenderError(f"theme: {self.theme_error}")
            engine = (layout or self.layout) if d.layout is not None else None
            ck = (key, self.theme_gen, engine)
            if ck in self._cache:
                return self._cache[ck]
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    scene = build_scene(apply_layout(d, self.theme, engine), self.theme)
                    svg = to_svg(scene)
            except Exception as exc:  # noqa: BLE001
                raise RenderError(_message(exc), sf.rel) from exc
            msgs = list(dict.fromkeys(str(w.message) for w in caught))
            out = (svg, {"overflow": scene.layout_overflow, "warnings": msgs, "missing_packs": _missing_packs(msgs)})
            self._cache[ck] = out
            return out

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    # summary --------------------------------------------------------------------------------------
    def summary(self) -> dict:
        from ..autolayout.engines import available, get_engine

        engines = []
        for name in sorted(available()):
            try:
                hint = get_engine(name).available()
            except Exception as exc:  # noqa: BLE001
                hint = _message(exc)
            engines.append({"name": name, "hint": hint})
        with self._lock:
            files = [{"path": sf.rel, "error": sf.error,
                      "diagrams": [{"key": self.key(rel, d), "id": d.id, "title": d.title, "auto": d.layout is not None}
                                   for d in sf.diagrams]}
                     for rel, sf in sorted(self.files.items())]
        import os

        theme_name = (self.theme.data.get("name") if self.theme else None) or Path(str(self.theme_ref or "default")).name
        return {"paths": [str(p) for p in self.paths], "theme": str(self.theme_ref or "default"), "theme_name": theme_name,
                "theme_error": self.theme_error, "layout": self.layout, "engines": engines, "files": files,
                "offline": os.environ.get("SPINAGRAM_OFFLINE") == "1"}
