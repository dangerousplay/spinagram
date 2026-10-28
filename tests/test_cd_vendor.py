"""Vendor service matching and the generic-icon hint (VND-01..05)."""
from __future__ import annotations

import json

import pytest

from spinagram import icons
from spinagram.engine import vendor

FAKE = {  # pack → (icon names, aliases); written as cached indexes
    "aws": (["aws-lambda", "amazon-ec2", "elastic-load-balancing", "amazon-simple-queue-service"],
            {"lambda": "aws-lambda", "ec2": "amazon-ec2", "load-balancing": "elastic-load-balancing",
             "sqs": "amazon-simple-queue-service"}),
    "gcp": (["cloud-run", "cloud-load-balancing", "pub-sub", "spanner"], {"load-balancing": "cloud-load-balancing"}),
    "logos": (["consul", "vault"], {}),  # registered, cached, but not a vendor pack (not in metadata.PROVIDERS)
}


@pytest.fixture
def packs(tmp_path, monkeypatch):
    """The registry with fake cached indexes for aws, gcp and logos; every other pack uncached. Fetching fails."""
    monkeypatch.setenv("SPINAGRAM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    def no_fetch(*a, **k):
        raise AssertionError("check must not fetch icon packs")

    monkeypatch.setattr(icons, "fetch", no_fetch)
    monkeypatch.setattr(icons, "_get", no_fetch)
    vendor.clear_cache()
    icons._INDEX_CACHE.clear()  # resolve() caches indexes by pack@version: keep the fakes out of other tests
    reg = icons.registry()
    for name, (names, aliases) in FAKE.items():
        p = reg[name]
        p.dir.mkdir(parents=True)
        (p.dir / "index.json").write_text(json.dumps({
            "pack": name, "icons": {n: {"light": f"{name}__{n}.svg"} for n in names}, "aliases": aliases}))
        for n in names:
            (p.dir / f"{name}__{n}.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    yield reg
    vendor.clear_cache()
    icons._INDEX_CACHE.clear()


MATCHES = [  # (id, title, expected ref)
    ("alias", "Lambda", "aws:lambda"),
    ("name", "aws lambda", "aws:aws-lambda"),                       # 2-word n-gram beats the 1-word alias
    ("case-and-camel", "AWS Lambda functions", "aws:aws-lambda"),
    ("three-words", "Elastic Load Balancing", "aws:elastic-load-balancing"),
    ("longest-wins-over-pack-order", "Cloud Run Lambda", "gcp:cloud-run"),
    ("tie-pack-a-z", "Load balancing", "aws:load-balancing"),       # aws and gcp both have it: aws first
    ("same-length-pack-a-z", "Spanner and Lambda", "aws:lambda"),   # equal length: pack A–Z, not title order
    ("one-hit", "Spanner and Consul", "gcp:spanner"),
    ("short-ngram-ignored", "EC2 fleet", None),                     # "ec2" has 3 chars (< 4)
    ("short-alias-ignored", "SQS", None),
    ("no-match", "Consul server", None),
    ("non-vendor-pack", "Consul", None),                            # logos is cached but not a vendor pack
    ("list-title", ["Pub", "Sub"], "gcp:pub-sub"),
    ("punctuation", "Lambda: worker", "aws:lambda"),
    ("none", None, None),
    ("empty", "", None),
]


@pytest.mark.parametrize("title,ref", [m[1:] for m in MATCHES], ids=[m[0] for m in MATCHES])
def test_match(packs, title, ref):
    assert vendor.match(title, packs) == ref


@pytest.mark.parametrize("title,ref", [m[1:] for m in MATCHES], ids=[m[0] for m in MATCHES])
def test_match_is_deterministic(packs, title, ref):
    assert {vendor.match(title, dict(reversed(list(packs.items())))) for _ in range(3)} == {ref}


def test_uncached_vendor_pack_is_skipped_without_fetching(packs):
    assert not (packs["azure"].dir / "index.json").exists()
    assert vendor.match("Azure Functions", packs) is None          # fetch would raise


def test_ngrams():
    assert vendor.ngrams("AWS Lambda edge worker") == [
        "aws-lambda-edge", "lambda-edge-worker", "aws-lambda", "lambda-edge", "edge-worker", "lambda", "edge",
        "worker"]


# ---- T17: hint and swap (VND-01, VND-04, VND-05) -------------------------------------------------------------------
def _theme(tmp_path, prefer: bool):
    from spinagram import Theme

    root = tmp_path / ("prefer" if prefer else "plain")
    (root / "icons").mkdir(parents=True)
    (root / "icons" / "gear.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"/>')
    (root / "theme.yaml").write_text(
        "extends: default\nicons:\n  dir: icons\n  pattern: '{name}.svg'\n"
        f"  prefer_vendor_for_services: {str(prefer).lower()}\n"
        "  alias: {fn: gear, lam: 'aws:lambda'}\n"
        "  fallback: {compute: [gear], serverless: ['aws:lambda']}\n")
    return Theme.load(root)


HINTS = [  # (id, icon, title, prefer, expected issue detail or None, expected drawn icon file)
    ("icon-dir", "gear", "Lambda", False, "'Lambda' matches aws:lambda; icon 'gear' is generic", "gear.svg"),
    ("theme-alias", "fn", "Lambda workers", False, "'Lambda workers' matches aws:lambda; icon 'fn' is generic",
     "gear.svg"),
    ("concept-chain", "concept:compute", "AWS Lambda", False,
     "'AWS Lambda' matches aws:aws-lambda; icon 'concept:compute' is generic", "gear.svg"),
    ("alias-to-the-service", "lam", "Lambda", False, None, "aws__aws-lambda.svg"),
    ("concept-to-the-service", "concept:serverless", "Lambda", False, None, "aws__aws-lambda.svg"),
    ("pack-ref-other-service", "gcp:cloud-run", "Lambda", False, None, "gcp__cloud-run.svg"),
    ("pack-ref", "aws:lambda", "Lambda", False, None, "aws__aws-lambda.svg"),
    ("no-service", "gear", "Consul server", False, None, "gear.svg"),
    ("no-icon", None, "Lambda", False, None, None),
    ("prefer-swaps", "gear", "Lambda", True, None, "aws__aws-lambda.svg"),
    ("prefer-swaps-concept", "concept:compute", "Cloud Run", True, None, "gcp__cloud-run.svg"),
    ("prefer-keeps-pack-ref", "gcp:cloud-run", "Lambda", True, None, "gcp__cloud-run.svg"),
    ("prefer-no-service", "gear", "Consul", True, None, "gear.svg"),
]


@pytest.mark.parametrize("icon,title,prefer,detail,drawn", [h[1:] for h in HINTS], ids=[h[0] for h in HINTS])
@pytest.mark.parametrize("laid_out", [False, True], ids=["hand", "engine"])
def test_hint_and_swap(packs, tmp_path, icon, title, prefer, detail, drawn, laid_out):
    from spinagram import Diagram, build_scene
    from spinagram.qa import check

    theme = _theme(tmp_path, prefer)
    d = Diagram("V", "Vendor")
    if laid_out:  # an engine-laid-out diagram: the hint runs on every scene
        d.box(title, id="n", icon=icon)
    else:
        d.box(title, id="n", icon=icon, x=200, y=200, w=400, h=160)
    sc = build_scene(d, theme)
    assert sc.laid_out == laid_out
    got = [(i.item, i.detail, i.severity) for i in check(sc) if i.kind == "icon-generic-for-service"]
    assert got == ([("n", detail, "P2")] if detail else [])
    s = sc.shapes()["n"]
    assert (s.icon.path.name if s.icon else None) == drawn
