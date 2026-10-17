"""Files the live editor reads and lists: spec counts, directory listings for the Open-folder dialog and
source files with their version (SHA-256 of the bytes) and newline style."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

SPEC_EXTS = {".yaml", ".yml", ".py"}
# folders never scanned or offered: generated, vendored or tool state
SKIP_DIRS = frozenset({"node_modules", "__pycache__", ".venv", "venv", "out", "dist", "build", "site-packages"})
MAX_SPECS = 2000  # a folder with more spec files loads the first ones by path and reports itself truncated
LANGUAGES = {".py": "python", ".css": "css", ".yaml": "yaml", ".yml": "yaml"}


def is_spec(p: Path) -> bool:
    return p.is_file() and p.suffix in SPEC_EXTS and not p.name.startswith("_")


def skipped(name: str) -> bool:
    """A folder the scan and the dialog leave out."""
    return name.startswith(".") or name in SKIP_DIRS


def resolve_dir(path: str | Path) -> Path:
    """``path`` as an absolute directory; ``NotADirectoryError("not a directory: <path>")`` otherwise."""
    p = Path(path).expanduser()
    try:
        p = p.resolve()
    except OSError:
        pass
    if not p.is_dir():
        raise NotADirectoryError(f"not a directory: {Path(path).expanduser()}")
    return p


def spec_count(folder: Path) -> int:
    """Spec files directly in ``folder`` (0 when it cannot be read)."""
    try:
        return sum(1 for f in folder.iterdir() if is_spec(f))
    except OSError:
        return 0


def list_dir(path: str | Path) -> dict:
    """One level of the Open-folder dialog: the folder, its parent and its visible subfolders with spec counts."""
    p = resolve_dir(path)
    dirs = []
    for c in sorted(p.iterdir(), key=lambda c: c.name.lower()):
        try:
            if c.is_dir() and not skipped(c.name):
                dirs.append({"name": c.name, "path": str(c), "specs": spec_count(c)})
        except OSError:
            continue
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "specs": spec_count(p),
            "dirs": dirs}


@dataclass
class SourceFile:
    path: Path
    text: str       # newlines normalised to \n for the editor
    version: str    # SHA-256 of the bytes on disk
    newline: str    # "\r\n" or "\n": restored on save
    language: str   # python | css | yaml | text


def version_of(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_source(path: Path) -> SourceFile:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    return SourceFile(path, text.replace("\r\n", "\n"), version_of(raw), newline,
                      LANGUAGES.get(path.suffix.lower(), "text"))
