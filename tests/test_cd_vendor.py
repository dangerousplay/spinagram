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
