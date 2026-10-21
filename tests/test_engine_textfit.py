"""Text fitting: token breaks, wrapping, shrink and grow (layout-engine TXT-01..09)."""
import re

import pytest

from spinagram import Theme
from spinagram.engine.textfit import BREAK_ON, break_token, wrap_fit
from spinagram.text import measure, wrap

FONT = Theme.load("default").font("heading", 700, 18)
CIDR = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?")

TOKENS = [
    ("hostname", "lb-pool-https-8081"),
    ("glob", "runner-*-x-template-*"),
    ("fqdn", "gitlab.node-a.example.internal"),
    ("url-path", "https://registry.example.com/v2/catalog"),
    ("cidr", "10.0.0.0/22"),
    ("cidr-list", "10.0.0.0/22·10.0.8.0/21"),
    ("ip-port", "10.20.30.40:8081"),
    ("unix-path", "/var/opt/gitlab/git-data/repositories"),
    ("dotted-svc", "svc.monitoring.cluster.local"),
    ("no-breaks", "averyveryverylongunbreakabletokenname"),
    ("short", "nginx"),
    ("middot", "8-members·nginx:8081·https"),
]
WIDTHS = [60, 120, 200]


def _scenarios():
    return [pytest.param(tok, w, id=f"{name}-{w}px") for name, tok in TOKENS for w in WIDTHS]


@pytest.mark.parametrize("token,width", _scenarios())
def test_break_token_keeps_text_and_breaks_only_after_safe_chars(token, width):
    lines = break_token(token, FONT, width)
    assert "".join(lines) == token                      # no hyphen or other character inserted (TXT-02)
    for ln in lines[:-1]:
        assert ln[-1] in BREAK_ON                       # every cut lands after a break character
    for m in CIDR.finditer(token):                      # TXT-03: IPv4/CIDR never split
        assert any(m.group(0) in ln for ln in lines)


@pytest.mark.parametrize("token,width", _scenarios())
def test_break_token_lines_fit_unless_unbreakable(token, width):
    lines = break_token(token, FONT, width)
    for ln in lines:
        if measure(ln, FONT) > width:                   # only a piece with no safe cut may exceed the width
            inner = [i + 1 for i, ch in enumerate(ln[:-1]) if ch in BREAK_ON]
            spans = [(m.start(), m.end()) for m in CIDR.finditer(ln)]
            assert all(any(a < c < b for a, b in spans) for c in inner)


def test_cidr_golden_stays_unbroken():  # TXT-03 golden from the roadmap
    lines = break_token("10.0.0.0/22·10.0.8.0/21", FONT, 40)
    assert lines == ["10.0.0.0/22·", "10.0.8.0/21"]


TEXTS = [
    ("words", "eight members behind one nginx pool"),
    ("token-in-sentence", "pool lb-pool-https-8081 serves port 8081"),
    ("cidr-list", "10.0.0.0/22 · 10.0.8.0/21"),
    ("one-long-token", "runner-autoscale-template-large-x86-64"),
    ("mixed", "managers default · 2x runner-*-x-* on gitlab.node-a.example.internal"),
]
LENGTH_WIDTHS = [166, 230]


@pytest.mark.parametrize("text,width",
                         [pytest.param(t, w, id=f"{n}-{w}px") for n, t in TEXTS for w in LENGTH_WIDTHS])
def test_wrap_fit_spaces_first_then_tokens(text, width):  # TXT-01
    lines = wrap_fit([text], FONT, width)
    assert " ".join(lines).replace(" ", "") == text.replace(" ", "")  # nothing lost or added
    for ln in lines:
        assert measure(ln, FONT) <= width or not any(c in BREAK_ON + " " for c in ln.strip()[:-1]) \
            or CIDR.fullmatch(ln.strip())
    if all(measure(w, FONT) <= width for w in text.split()):  # spaces alone suffice: no token is cut
        assert set(lines) <= set(_space_wrap(text, width))


def _space_wrap(text, width):
    return wrap(text, FONT, width)


@pytest.mark.parametrize("n", [10, 20, 30, 40, 50, 60], ids=lambda n: f"{n}chars")
def test_wrap_fit_growing_token_lengths_fit_166px(n):  # roadmap acceptance: tokens of 10..60 chars
    token = "-".join(["node"] * 60)[:n]
    lines = wrap_fit([token], FONT, 166)
    assert all(measure(ln, FONT) <= 166 for ln in lines)
    assert "".join(lines) == token


def test_wrap_fit_keeps_empty_paragraph():
    assert wrap_fit(["a", "", "b"], FONT, 100) == ["a", "", "b"]
