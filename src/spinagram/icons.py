"""Icon packs: cloud/vendor icon sets downloaded on demand and referenced as ``pack:name``.

A *pack* is declared in YAML (built-ins in ``spinagram/icon_packs/*.yaml``; users add their own)
and points at a source:

* ``zip``     — an archive URL (``file://`` works too)
* ``npm``     — a package tarball from the npm registry (``package`` + ``version``)
* ``github``  — files of a GitHub repository (``repo``, ``ref``), listed with the trees API
* ``listing`` — files named on an index page (``url`` + ``pattern`` regex, optional ``base``)
* ``dir``     — a local directory (nothing is downloaded)

``alias`` adds curated short names (``s3: amazon-simple-storage-service``). ``rules`` map each source path to an icon name with a regex: the first rule that matches wins;
its ``name`` template is filled with the named groups and normalised to kebab-case
(``AmazonEC2`` → ``amazon-ec2``). A rule may set ``tone: dark`` (variant used on dark fills) and
``aliases`` (extra templates). ``strip`` regexes add short aliases (``^amazon-`` → ``ec2``).
``current_color`` (``{light: "#000", dark: "#fff"}``) paints SVGs drawn in ``currentColor`` — an ``<image>``
has no inherited colour, so they would render black on every fill — and gives each one without a dark
variant a copy in the ``dark`` colour.

Files are copied to ``$SPINAGRAM_CACHE`` (default ``~/.cache/spinagram/icons``) as
``<pack>/<version>/<pack>__<name>[__dark].<ext>`` with an ``index.json``; specs then use
``icon: aws:ec2``. A missing pack is fetched on first use unless ``SPINAGRAM_OFFLINE=1``.

Registries are merged in order: built-in < ``~/.config/spinagram/icons.yaml`` <
``./spinagram-icons.yaml`` < ``$SPINAGRAM_ICON_PACKS`` (a file). ``spinagram icons add``
writes the user (or ``--project``) registry.
"""
from __future__ import annotations

import fnmatch
import io
import json
import os
import re
import shutil
import tarfile
import threading
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

BUILTIN_DIR = Path(__file__).parent / "icon_packs"
EXTS = (".svg", ".png")


def cache_root() -> Path:
    return Path(os.environ.get("SPINAGRAM_CACHE") or Path.home() / ".cache" / "spinagram" / "icons")


def user_registry() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "spinagram" / "icons.yaml"


PROJECT_REGISTRY = "spinagram-icons.yaml"


def kebab(s: str) -> str:
    """``AmazonAPIGateway`` → ``amazon-api-gateway``; ``compute_engine`` → ``compute-engine``."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "-", s)
    s = re.sub(r"[^A-Za-z0-9]+", "-", s)
    return s.strip("-").lower()


@dataclass
class Rule:
    match: re.Pattern
    name: str = "{stem}"
    tone: str = "light"
    aliases: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, d: dict) -> "Rule":
        return cls(re.compile(d["match"]), d.get("name", "{stem}"), d.get("tone", "light"), list(d.get("aliases") or []))


@dataclass
class Pack:
    name: str
    title: str
    source: dict[str, Any]
    rules: list[Rule]
    strip: list[str] = field(default_factory=list)
    license: str = ""
    homepage: str = ""
    origin: str = "builtin"
    alias: dict[str, str] = field(default_factory=dict)  # curated short names: {s3: amazon-simple-storage-service}
    vectorize: bool = True  # PNG icons → SVG when faithful (see spinagram.vectorize)
    current_color: dict[str, str] = field(default_factory=dict)  # tone → colour for `currentColor` SVGs

    @classmethod
    def parse(cls, name: str, d: dict, origin: str) -> "Pack":
        rules = [Rule.parse(r) for r in d.get("rules") or []] or [
            Rule(re.compile(r"(?:.*/)?(?P<stem>[^/]+)\.(?:svg|png)$"))]
        return cls(name, d.get("title", name), dict(d.get("source") or {}), rules, list(d.get("strip") or []),
                   d.get("license", ""), d.get("homepage", ""), origin,
                   {kebab(k): kebab(v) for k, v in (d.get("alias") or {}).items()}, bool(d.get("vectorize", True)),
                   dict(d.get("current_color") or {}))

    @property
    def version(self) -> str:
        s = self.source
        return str(s.get("version") or s.get("ref") or ("local" if s.get("type") == "dir" else "latest"))

    @property
    def dir(self) -> Path:
        return cache_root() / self.name / re.sub(r"[^\w.-]+", "_", self.version)

    # naming -------------------------------------------------------------------------------------
    def classify(self, path: str) -> tuple[str, str, list[str], int] | None:
        """Source path → (name, tone, aliases, rule index), or None when no rule matches."""
        for i, r in enumerate(self.rules):
            m = r.match.search(path)
            if not m:
                continue
            groups = {k: v for k, v in m.groupdict().items() if v is not None}
            name = kebab(r.name.format(**groups))
            aliases = [kebab(a.format(**groups)) for a in r.aliases]
            for pat in self.strip:
                short = re.sub(pat, "", name)
                if short and short != name:
                    aliases.append(short)
            return name, r.tone, aliases, i
        return None


# registry -----------------------------------------------------------------------------------------
def _load_file(path: Path, origin: str) -> dict[str, Pack]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    packs = data.get("packs", data) if isinstance(data, dict) else {}
    return {name: Pack.parse(name, d, origin) for name, d in packs.items()}


def registry(cwd: Path | None = None) -> dict[str, Pack]:
    packs: dict[str, Pack] = {}
    for f in sorted(BUILTIN_DIR.glob("*.yaml")):
        packs.update(_load_file(f, "builtin"))
    for f, origin in ((user_registry(), "user"), ((cwd or Path.cwd()) / PROJECT_REGISTRY, "project")):
        if f.exists():
            packs.update(_load_file(f, origin))
    env = os.environ.get("SPINAGRAM_ICON_PACKS")
    if env and Path(env).exists():
        packs.update(_load_file(Path(env), "env"))
    return packs


def register(name: str, source: dict[str, Any], *, rules: list[dict] | None = None, strip: list[str] | None = None,
             title: str = "", license: str = "", project: bool = False) -> Path:
    """Add (or replace) a pack in the user registry, or ``./spinagram-icons.yaml`` with ``project``."""
    path = Path(PROJECT_REGISTRY) if project else user_registry()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    data = data or {"packs": {}}
    entry: dict[str, Any] = {"title": title or name, "source": source}
    if license:
        entry["license"] = license
    if rules:
        entry["rules"] = rules
    if strip:
        entry["strip"] = strip
    data.setdefault("packs", {})[name] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def unregister(name: str, *, project: bool = False) -> bool:
    path = Path(PROJECT_REGISTRY) if project else user_registry()
    if not path.exists():
        return False
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if name not in (data.get("packs") or {}):
        return False
    del data["packs"][name]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return True


# sources ----------------------------------------------------------------------------------------
def _get(url: str, timeout: int = 300) -> bytes:
    headers = {"User-Agent": "spinagram"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return r.read()


def _npm_tarball(s: dict) -> str:
    """Tarball URL of ``package@version`` from any npm registry (npmjs, Artifactory, Nexus, Verdaccio).

    Reads the full package document (``/<@scope%2fname>``) — every registry serves it, while the
    per-version endpoint is not universal — and resolves dist-tags (``latest``) to a version.
    """
    from urllib.parse import quote

    registry = str(s.get("registry") or "https://registry.npmjs.org/").rstrip("/")
    doc = json.loads(_get(f"{registry}/{quote(s['package'], safe='@')}"))
    want = str(s.get("version") or "latest")
    version = doc.get("dist-tags", {}).get(want, want)
    if version not in doc.get("versions", {}):
        raise ValueError(f"npm {s['package']}@{want}: not found in {registry} "
                         f"(versions: {', '.join(list(doc.get('versions', {}))[-5:])})")
    return doc["versions"][version]["dist"]["tarball"]


def _included(path: str, include: list[str]) -> bool:
    return not include or any(fnmatch.fnmatch(path, g) for g in include)


def _iter_source(pack: Pack) -> Iterator[tuple[str, bytes]]:
    """Yield (path inside the source, bytes) for every icon file the source offers."""
    s = pack.source
    kind = s.get("type")
    include = list(s.get("include") or [])
    if kind == "dir":
        root = Path(s["path"]).expanduser()
        for f in sorted(root.rglob("*")):
            rel = f.relative_to(root).as_posix()
            if f.suffix.lower() in EXTS and _included(rel, include):
                yield rel, f.read_bytes()
    elif kind in ("zip", "npm"):
        if kind == "npm":
            blob = _get(_npm_tarball(s))
        else:
            blob = _get(s["url"])
        if blob[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                for n in z.namelist():
                    if n.lower().endswith(EXTS) and _included(n, include):
                        yield n, z.read(n)
        else:
            with tarfile.open(fileobj=io.BytesIO(blob)) as t:
                for m in t.getmembers():
                    if m.isfile() and m.name.lower().endswith(EXTS) and _included(m.name, include):
                        yield m.name, t.extractfile(m).read()
    elif kind == "listing":
        yield from _iter_listing(s, include)
    elif kind == "github":
        from urllib.parse import quote

        repo, ref = s["repo"], s.get("ref", "main")
        tree = json.loads(_get(f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"))
        # one request per file: skip what no rule names before downloading it
        paths = [e["path"] for e in tree.get("tree", []) if e.get("type") == "blob"
                 and e["path"].lower().endswith(EXTS) and _included(e["path"], include) and pack.classify(e["path"])]
        with ThreadPoolExecutor(8) as ex:
            blobs = ex.map(lambda p: _get(f"https://raw.githubusercontent.com/{repo}/{ref}/{quote(p)}"), paths)
            yield from zip(paths, blobs)
    else:
        raise ValueError(f"icon pack {pack.name!r}: unknown source type {kind!r} (zip, npm, github, listing, dir)")


def _iter_listing(s: dict, include: list[str]) -> Iterator[tuple[str, bytes]]:
    """Icons named on an index page: ``pattern`` (group ``path``, else group 1) finds each file,
    fetched from ``base`` (default: the page URL). Paths may be URL-encoded; a file that fails to
    download is skipped with one warning, so a single dead link does not lose the whole pack."""
    from urllib.parse import quote, unquote, urljoin

    page = s["url"]
    html = _get(page).decode("utf-8", "replace")
    rx = re.compile(s["pattern"])
    paths: list[str] = []
    for m in rx.finditer(html):
        p = unquote(m.group("path") if "path" in rx.groupindex else m.group(1))
        if p.lower().endswith(EXTS) and _included(p, include) and p not in paths:
            paths.append(p)
    if not paths:
        raise ValueError(f"listing {page}: pattern {s['pattern']!r} found no icons")
    base = s.get("base") or page
    failed: list[str] = []

    def get(p: str) -> bytes | None:
        try:
            return _get(urljoin(base, quote(p)), timeout=60)
        except Exception:  # noqa: BLE001 — skip one dead link, report below
            failed.append(p)
            return None

    with ThreadPoolExecutor(16) as ex:
        for p, blob in zip(paths, ex.map(get, paths)):
            if blob is not None:
                yield p, blob
    if failed:
        import warnings

        warnings.warn(f"{len(failed)} of {len(paths)} icons failed to download from {page} "
                      f"(e.g. {failed[0]})", stacklevel=3)


# fetch / index ----------------------------------------------------------------------------------
AUTO_FETCH = True  # resolving an icon of a missing pack downloads it; `spinagram serve` turns this off

_FETCH_LOCKS: dict[str, threading.Lock] = {}
_FETCH_LOCKS_GUARD = threading.Lock()


def fetch(pack: Pack, *, force: bool = False) -> Path:
    """Download (or index) a pack into the cache; returns its directory.

    One fetch per pack directory at a time (a concurrent caller waits, then reuses the result unless
    ``force``): two threads writing the same ``.tmp`` directory would corrupt each other."""
    d = pack.dir
    with _FETCH_LOCKS_GUARD:
        lock = _FETCH_LOCKS.setdefault(str(d), threading.Lock())
    with lock:
        if (d / "index.json").exists() and not force:
            return d
        return _fetch(pack, d)


def _fetch(pack: Pack, d: Path) -> Path:
    tmp = d.with_name(d.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    icons: dict[str, dict[str, str]] = {}
    aliases: dict[str, str] = {}
    found = []
    for path, data in _iter_source(pack):
        got = pack.classify(path)
        if got:
            found.append((got[3], path, data, got))
    found.sort(key=lambda f: (f[0], f[1]))  # rule order = preference, then path for a stable result
    for _, path, data, (name, tone, extra, _) in found:
        entry = icons.setdefault(name, {})
        if tone in entry:
            continue
        ext = Path(path).suffix.lower()
        fname = f"{pack.name}__{name}{'__dark' if tone == 'dark' else ''}{ext}"
        (tmp / fname).write_bytes(data)
        entry[tone] = fname
        entry.setdefault("source", path)
        for a in extra:
            aliases.setdefault(a, name)
    _paint_current_color(pack, tmp, icons)
    for a in list(aliases):
        if a in icons:
            del aliases[a]
    for a, target in pack.alias.items():  # curated aliases win over derived ones
        target = target if target in icons else aliases.get(target, target)  # may name a derived alias
        if target in icons and a not in icons:
            aliases[a] = target
    index = {"pack": pack.name, "title": pack.title, "version": pack.version, "license": pack.license,
             "homepage": pack.homepage, "icons": dict(sorted(icons.items())), "aliases": dict(sorted(aliases.items()))}
    _vectorize_index(pack, tmp, index)
    (tmp / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(d, ignore_errors=True)
    tmp.rename(d)
    return d


def _paint_current_color(pack: Pack, d: Path, icons: dict[str, dict[str, str]]) -> None:
    """Fix the colour of ``currentColor`` SVGs per tone, adding the dark variant they lack."""
    colors = pack.current_color
    if not colors:
        return
    for name, entry in icons.items():
        light = entry.get("light")
        if not light or not light.endswith(".svg"):
            continue
        text = (d / light).read_text(encoding="utf-8")
        if "currentColor" not in text:
            continue
        if colors.get("light"):
            (d / light).write_text(text.replace("currentColor", colors["light"]), encoding="utf-8")
        if colors.get("dark") and "dark" not in entry:
            dark = f"{pack.name}__{name}__dark.svg"
            (d / dark).write_text(text.replace("currentColor", colors["dark"]), encoding="utf-8")
            entry["dark"] = dark


def _vectorize_index(pack: Pack, d: Path, idx: dict) -> bool:
    """Trace the pack's PNG icons into SVG (fidelity-gated); entries keep the PNG under ``raster``.

    Returns True when the index changed. Marks the index with ``vectorized`` = params version so an
    index built without vectorization (or with older params) is upgraded in place, no download.
    """
    from . import vectorize

    if not vectorize.enabled(pack.vectorize) or idx.get("vectorized") == vectorize.PARAMS_VERSION:
        return False
    stats = {"accepted": 0, "rejected": 0}
    for entry in idx["icons"].values():
        raster = entry.setdefault("raster", {})
        for tone in ("light", "dark"):
            fname = raster.get(tone) or entry.get(tone)
            if not fname or not fname.endswith(".png"):
                continue
            res = vectorize.vectorize_bytes((d / fname).read_bytes())
            entry.setdefault("vector", {})[tone] = asdict(res.score) if res.score else None
            if res.accepted:
                svg_name = fname[:-4] + ".svg"
                (d / svg_name).write_text(res.svg, encoding="utf-8")
                raster[tone] = fname
                entry[tone] = svg_name
                stats["accepted"] += 1
            else:
                stats["rejected"] += 1
        if not raster:
            del entry["raster"]
    idx["vectorized"] = vectorize.PARAMS_VERSION
    idx["vector_stats"] = stats
    return True


def index(pack: Pack, *, auto_fetch: bool = True) -> dict | None:
    f = pack.dir / "index.json"
    if not f.exists():
        if not auto_fetch or not AUTO_FETCH or os.environ.get("SPINAGRAM_OFFLINE") == "1":
            return None
        fetch(pack)
    idx = json.loads(f.read_text(encoding="utf-8"))
    if _vectorize_index(pack, pack.dir, idx):
        f.write_text(json.dumps(idx, indent=1, ensure_ascii=False), encoding="utf-8")
    return idx


_INDEX_CACHE: dict[str, dict | None] = {}


def resolve(ref: str, tone: str = "light", *, packs: dict[str, Pack] | None = None) -> Path | None:
    """``aws:ec2`` → cached file (dark variant when ``tone='dark'`` and the pack has one)."""
    if ":" not in ref:
        return None
    pname, name = ref.split(":", 1)
    packs = packs if packs is not None else registry()
    pack = packs.get(pname)
    if pack is None:
        return None
    key = f"{pack.name}@{pack.version}"
    if key not in _INDEX_CACHE:
        try:
            _INDEX_CACHE[key] = index(pack)
        except Exception as exc:  # noqa: BLE001 — unreachable/unpublished pack: warn once, fall back to local icons
            import warnings

            warnings.warn(f"icon pack {pack.name!r} unavailable ({exc}); using local icons", stacklevel=2)
            _INDEX_CACHE[key] = None
    idx = _INDEX_CACHE[key]
    if not idx:
        return None
    n = kebab(name)
    # the registry's curated aliases apply at once, without downloading the pack again
    entry = idx["icons"].get(n) or idx["icons"].get(idx["aliases"].get(n, "")) \
        or idx["icons"].get(pack.alias.get(n, ""))
    if not entry:
        return None
    fname = entry.get("dark" if tone == "dark" else "light") or entry.get("light") or entry.get("dark")
    return pack.dir / fname if fname else None


def search(query: str, packs: Iterable[Pack]) -> list[tuple[str, str, str]]:
    """(pack, name, matched-as) for every icon whose name or alias contains all query words."""
    words = [kebab(w) for w in query.split() if w]
    out = []
    for p in packs:
        idx = index(p, auto_fetch=False)
        if not idx:
            continue
        for name in idx["icons"]:
            if all(w in name for w in words):
                out.append((p.name, name, name))
        for alias, target in idx["aliases"].items():
            if all(w in alias for w in words):
                out.append((p.name, alias, target))
    return out
