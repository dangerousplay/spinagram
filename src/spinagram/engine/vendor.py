"""Cloud services named in node titles, matched against cached vendor icon packs (VND-02, VND-03).

Vendor packs are the packs of ``metadata.PROVIDERS`` that are registered and already cached; this module never
downloads one, so ``check`` stays offline."""
from __future__ import annotations

from .. import icons
from ..metadata import PROVIDERS

MIN_CHARS = 4  # shorter n-grams ("ec2", "sqs") match too much
_NAMES: dict[str, frozenset[str]] = {}  # pack dir → icon names and aliases (cached indexes only)


def clear_cache() -> None:
    _NAMES.clear()


def ngrams(title) -> list[str]:
    """Contiguous 1–3 word kebab n-grams of ``title`` with at least ``MIN_CHARS`` characters, longest first, then
    left to right."""
    text = " ".join(title) if isinstance(title, (list, tuple)) else str(title or "")
    words = [w for w in icons.kebab(text).split("-") if w]
    out = []
    for size in (3, 2, 1):
        out += ["-".join(words[i:i + size]) for i in range(len(words) - size + 1)]
    return [g for g in out if len(g) >= MIN_CHARS]


def _names(pack: icons.Pack) -> frozenset[str] | None:
    key = str(pack.dir)
    if key not in _NAMES:
        idx = icons.index(pack, auto_fetch=False)
        if not idx:
            return None  # not cached: skipped (and looked at again next time)
        known = set(idx.get("icons") or {}) | set(idx.get("aliases") or {})
        _NAMES[key] = frozenset(known | {a for a, t in pack.alias.items() if t in known})  # curated: as resolve
    return _NAMES[key]


def match(title, packs: dict[str, icons.Pack] | None = None) -> str | None:
    """``pack:name`` of the vendor icon a node title names, else None. The longest n-gram wins; among n-grams of
    the same length, the pack name A–Z, then the leftmost n-gram."""
    grams = ngrams(title)
    if not grams:
        return None
    packs = icons.registry() if packs is None else packs
    vendors = [(p, names) for p in sorted(n for n in packs if n in PROVIDERS)
               if (names := _names(packs[p])) is not None]
    for size in (3, 2, 1):
        same = [g for g in grams if g.count("-") == size - 1]
        for pack, names in vendors:
            hit = next((g for g in same if g in names), None)
            if hit is not None:
                return f"{pack}:{hit}"
    return None
