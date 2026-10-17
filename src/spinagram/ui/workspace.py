"""The specs a ``serve`` session watches: loading, rendering to SVG, caching and invalidation."""
from __future__ import annotations

import contextlib
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
from . import files as fsx
from .files import SPEC_EXTS  # noqa: F401  (re-exported: older imports)


def _missing_packs(messages: list[str]) -> list[str]:
    """Packs named in "icon 'pack:name' not found" warnings that are registered but not downloaded."""
    from .. import icons

    refs = {m.group(1) for msg in messages for m in [re.search(r"icon '([\w.-]+):", msg)] if m}
    if not refs:
        return []
    reg = icons.registry()
    return sorted(r for r in refs if r in reg and not (reg[r].dir / "index.json").exists())


def geometry(laid: Diagram, scene) -> dict:
    """Where each styled element sits in the scene, keyed like the CSS report (``node:<id>``, ...)."""
    from ..scene import Connector, Shape, Text

    zones = {f"z{i}": z.gid for i, z in enumerate(laid.zones) if z.gid}
    out: dict[str, dict] = {"diagram": {"box": [0, 0, scene.width, scene.height]}}
    nodes = {n.id for n in laid.nodes}
    for it in scene.items:
        if isinstance(it, Shape) and it.id in zones:
            out[f"group:{zones[it.id]}"] = {"box": [it.x, it.y, it.w, it.h]}
        elif isinstance(it, Shape) and it.id in nodes:
            out[f"node:{it.id}"] = {"box": [it.x, it.y, it.w, it.h]}
        elif isinstance(it, Text) and it.id in nodes:
            out[f"node:{it.id}"] = {"box": [it.x - (it.width or 0) * {"middle": .5, "end": 1}.get(it.anchor, 0), it.top,
                                            it.width or 0, it.block.height]}
        elif isinstance(it, Connector) and it.id[1:].isdigit():
            g = {"points": [list(p) for p in it.points], "route": it.route}
            if it.label is not None:
                g["label"] = [it.label.x, it.label.y, it.label.w, it.label.h]
            out[f"edge:{it.id[1:]}"] = g
    return {"geometry": out, "size": [scene.width, scene.height]}


class VersionConflict(Exception):
    """A save sent a version the file no longer has; ``current`` is the version on disk."""

    def __init__(self, current: str):
        super().__init__("the file changed since it was read")
        self.current = current


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
        self.truncated = False  # the last scan hit files.MAX_SPECS
        self._sheets: dict[str, list[Path]] = {}  # diagram key → its stylesheet files, kept while its spec is broken
        self._cache: dict[tuple, str] = {}
        self._geom: dict[tuple, dict] = {}
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
        """Spec files under the roots: a file root itself, every spec under a directory root (recursively,
        names sorted, a folder's files before its subfolders, skipped folders left out), at most
        ``files.MAX_SPECS`` in all (``truncated`` tells)."""
        import os

        found: list[Path] = []
        cap = fsx.MAX_SPECS
        self.truncated = False
        for p in self.paths:
            if not p.is_dir():
                found += [p] if fsx.is_spec(p) else []
                continue
            for folder, dirs, names in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not fsx.skipped(d))
                for n in sorted(names):
                    f = Path(folder) / n
                    if fsx.is_spec(f):
                        if len(found) >= cap:
                            self.truncated = True
                            return found
                        found.append(f)
        return found

    def contains(self, path: Path) -> bool:
        """A file root, or a path under a directory root that is not inside a skipped folder."""
        path = Path(path).resolve()
        for p in self.paths:
            if p.is_dir() and path.is_relative_to(p):
                return not any(fsx.skipped(part) for part in path.relative_to(p).parts[:-1])
            if path == p:
                return True
        return False

    def open(self, path: str | Path) -> None:
        """Make ``path`` the only root and load its specs; a path that is not a directory changes nothing."""
        root = fsx.resolve_dir(path)  # raises NotADirectoryError("not a directory: ...")
        with self._lock:
            self.paths = [root]
            self.files = {}
            self._sheets = {}
            self._cache.clear()
            self._geom.clear()
            self.rescan()

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
                    self._remember(rel)
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
            self._geom.clear()

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
                self._remember(rel)
                keys += [self.key(rel, d) for d in new.diagrams]
            self._drop(keys)
            return sorted(set(keys))

    def _drop(self, keys: list[str]) -> None:
        self._cache = {k: v for k, v in self._cache.items() if k[0] not in keys}
        self._geom = {k: v for k, v in self._geom.items() if k[0] not in keys}

    @staticmethod
    def sheet_path(d: Diagram, sheet: str) -> Path | None:
        """The file a ``stylesheets`` entry names (relative to the spec), or None for CSS text."""
        if "{" in sheet:
            return None
        p = Path(sheet).expanduser()
        if not p.is_absolute():
            base = Path(d.base_dir) if d.base_dir is not None else Path.cwd()
            p = base / p if (base / p).exists() or not p.exists() else p
        return p.resolve()

    def stylesheet_users(self) -> dict[Path, set[str]]:
        """Stylesheet files referenced by loaded diagrams (existing or not) → the diagram keys using them."""
        out: dict[Path, set[str]] = {}
        with self._lock:
            for rel, sf in self.files.items():
                for d in sf.diagrams:
                    for sheet in d.stylesheets:
                        p = self.sheet_path(d, sheet)
                        if p is not None:
                            out.setdefault(p, set()).add(self.key(rel, d))
        return out

    # sources (live editor) ------------------------------------------------------------------------
    def display(self, path: Path) -> str:
        """How the editor names a file, unique across roots (saves are addressed by it): relative to the root
        when one root is open, absolute when several are or the file is outside them."""
        if len(self.paths) > 1:
            return str(path)
        for p in self.paths:
            if p.is_dir() and path.is_relative_to(p):
                return path.relative_to(p).as_posix()
            if path == p:
                return path.name
        return str(path)

    def _sheets_of(self, d: Diagram) -> list[Path]:
        out: list[Path] = []
        for sheet in d.stylesheets:
            p = self.sheet_path(d, sheet)
            if p is not None and p not in out:
                out.append(p)
        return out

    def _remember(self, rel: str) -> None:
        """Note the stylesheet files of a spec that loaded, so its tabs survive a later broken save."""
        sf = self.files.get(rel)
        if sf is not None and not sf.error:
            for k in [k for k in self._sheets if k.startswith(f"{rel}#")]:
                del self._sheets[k]
            for d in sf.diagrams:
                self._sheets[self.key(rel, d)] = self._sheets_of(d)

    def source_paths(self, key: str) -> list[Path]:
        """The spec file of a diagram, then the existing stylesheet files of its cascade, in order, once each.
        A spec that fails to load lists the stylesheets it had when it last loaded. Raises ``KeyError`` for an
        unknown diagram."""
        with self._lock:
            sf, d = self.find(key)
            if d is None and not sf.error:
                raise KeyError(key)
            sheets = self._sheets_of(d) if d is not None else self._sheets.get(key, [])
            out = [sf.path.resolve()]
            for p in sheets:
                if p.is_file() and p not in out:
                    out.append(p)
            return out

    def editable(self) -> dict[str, Path]:
        """Display path → file, for every file a loaded diagram's source lists (the only files ``write`` touches)."""
        out: dict[str, Path] = {}
        with self._lock:
            keys = [self.key(rel, d) for rel, sf in self.files.items() for d in sf.diagrams]
            for rel, sf in self.files.items():
                if sf.error:  # a broken spec: its last known diagrams keep their stylesheets editable
                    keys += [k for k in self._sheets if k.startswith(f"{rel}#")] or [f"{rel}#"]
            for key in keys:
                for p in self.source_paths(key):
                    out[self.display(p)] = p
        return out

    def write(self, path: str, text: str, version: str) -> str:
        """Save editor text to a listed file if it still has ``version``; returns the new version.

        Keeps the file's newline style and permissions and replaces it atomically (temp file in the same
        folder, then rename). Raises ``PermissionError`` for a file no diagram lists and ``VersionConflict``
        when the file changed since it was read."""
        import os
        import stat
        import tempfile

        with self._lock:
            target = self.editable().get(path)
            if target is None:
                raise PermissionError(f"not an editable file: {path}")
            raw = target.read_bytes()
            current = fsx.version_of(raw)
            if current != version:
                raise VersionConflict(current)
            newline = "\r\n" if b"\r\n" in raw else "\n"
            data = text.replace("\r\n", "\n").replace("\n", newline).encode("utf-8")
            fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.chmod(tmp, stat.S_IMODE(target.stat().st_mode))
                os.replace(tmp, target)
            except BaseException:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
                raise
            return fsx.version_of(data)

    def source(self, key: str) -> list[dict]:
        """``source_paths`` read for the editor: display path, language, text (LF newlines) and version."""
        out = []
        for p in self.source_paths(key):
            src = fsx.read_source(p)
            out.append({"path": self.display(p), "language": src.language, "text": src.text, "version": src.version})
        return out

    def stylesheets_changed(self, changed: list[Path]) -> list[str]:
        """Forget renders of the diagrams whose cascade includes a changed stylesheet; returns their keys."""
        users = self.stylesheet_users()
        keys = sorted({k for c in changed for k in users.get(c.resolve(), ())})
        with self._lock:
            self._drop(keys)
        return keys

    def watch_dirs(self, theme_roots: list[Path]) -> set[Path]:
        """Folders to watch: spec folders, the theme chain and folders of stylesheets referenced elsewhere."""
        dirs = self.spec_dirs() | set(theme_roots)
        for p in self.stylesheet_users():
            if not any(p.is_relative_to(d) for d in dirs) and p.parent.is_dir():
                dirs.add(p.parent)
        return dirs

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
            engine = (layout or self.layout) if d.auto else None
            ck = (key, self.theme_gen, engine)
            if ck in self._cache:
                return self._cache[ck]
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    laid = apply_layout(d, self.theme, engine)
                    scene = build_scene(laid, self.theme)
                    svg = to_svg(scene)
            except Exception as exc:  # noqa: BLE001
                raise RenderError(_message(exc), sf.rel) from exc
            msgs = list(dict.fromkeys(str(w.message) for w in caught))
            out = (svg, {"overflow": scene.layout_overflow, "warnings": msgs, "missing_packs": _missing_packs(msgs)})
            self._cache[ck] = out
            self._geom[ck] = geometry(laid, scene)
            return out

    def styles(self, key: str, layout: str | None = None) -> dict:
        """The CSS inspector payload of one diagram: :func:`spinagram.css.inspect` plus ``geometry`` (scene
        coordinates per element key: ``box`` [x, y, w, h], or ``points`` and ``route`` for edges) and the
        scene ``size``. Raises like :meth:`render`."""
        from .. import css

        with self._lock:
            self.render(key, layout)
            sf, d = self.find(key)
            engine = (layout or self.layout) if d.auto else None
            geom = self._geom[(key, self.theme_gen, engine)]
            try:
                report = css.inspect(d, self.theme)
            except Exception as exc:  # noqa: BLE001
                raise RenderError(_message(exc), sf.rel) from exc
            return {**report, **geom}

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()
            self._geom.clear()

    # summary --------------------------------------------------------------------------------------
    def summary(self) -> dict:
        from ..autolayout.engines import available, get_engine
        from ..metadata import effective_category, effective_tags

        engines = []
        for name in sorted(available()):
            try:
                hint = get_engine(name).available()
            except Exception as exc:  # noqa: BLE001
                hint = _message(exc)
            engines.append({"name": name, "hint": hint})
        with self._lock:
            files = [{"path": sf.rel, "error": sf.error,
                      "diagrams": [{"key": self.key(rel, d), "id": d.id, "title": d.title, "auto": d.auto,
                                    "subtitle": d.subtitle, "category": effective_category(d),
                                    "tags": effective_tags(d)}
                                   for d in sf.diagrams]}
                     for rel, sf in sorted(self.files.items())]
        import os

        theme_name = (self.theme.data.get("name") if self.theme else None) or Path(str(self.theme_ref or "default")).name
        return {"paths": [str(p) for p in self.paths], "truncated": self.truncated,
                "theme": str(self.theme_ref or "default"), "theme_name": theme_name,
                "theme_error": self.theme_error, "layout": self.layout, "engines": engines, "files": files,
                "offline": os.environ.get("SPINAGRAM_OFFLINE") == "1"}
