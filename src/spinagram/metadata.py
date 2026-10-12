"""Catalog metadata: a diagram's effective tags and category, declared or inferred from its icons.

Declared metadata comes from ``Diagram.category`` and ``Diagram.tags``. Icons from the vendor packs add
provider tags (``aws:s3`` → ``aws``), and a diagram without a declared category falls into its dominant
provider, so existing diagrams group by cloud with no edits. Used by the CLI filters and ``serve``.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .model import Diagram

# icon pack prefix: (provider tag, display name)
PROVIDERS: dict[str, tuple[str, str]] = {
    "aws": ("aws", "AWS"),
    "gcp": ("gcp", "Google Cloud"),
    "k8s": ("kubernetes", "Kubernetes"),
    "azure": ("azure", "Azure"),
    "oci": ("oci", "OCI"),
    "openstack": ("openstack", "OpenStack"),
}
NAMES = dict(PROVIDERS.values())


def _provider(icon: str | None) -> str | None:
    pack, sep, _ = (icon or "").partition(":")
    return PROVIDERS[pack][0] if sep and pack in PROVIDERS else None


def provider_counts(d: Diagram) -> Counter[str]:
    """Icon references per provider tag: node, group and zone icons, plus ``aws-*`` zone styles."""
    refs: list[str | None] = [_provider(n.icon) for n in d.nodes]
    for g in d.groups:
        refs.append(_provider(g.icon))
        refs.append("aws" if (g.style or "").startswith("aws-") else None)
    for z in d.zones:
        refs.append(_provider(z.icon))
        refs.append("aws" if z.color.startswith("aws-") else None)
    return Counter(r for r in refs if r)


def effective_tags(d: Diagram) -> list[str]:
    """Declared tags plus inferred provider tags, sorted."""
    return sorted(set(d.tags) | set(provider_counts(d)))


def effective_category(d: Diagram) -> str:
    """The declared category, else the dominant provider's name (ties: first tag A-Z), else ``""``."""
    if d.category:
        return d.category
    counts = provider_counts(d)
    if not counts:
        return ""
    tag = min(counts, key=lambda t: (-counts[t], t))
    return NAMES[tag]


def matches(d: Diagram, tags: Iterable[str] = (), category: str | None = None) -> bool:
    """``d`` carries every tag (case-insensitive) and, when given, has this category (case-insensitive)."""
    want = {t.strip().lower() for t in tags} - {""}
    if not want <= set(effective_tags(d)):
        return False
    return category is None or effective_category(d).lower() == category.strip().lower()
