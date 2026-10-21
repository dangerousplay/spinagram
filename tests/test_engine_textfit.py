"""Text fitting: token breaks, wrapping, shrink and grow (layout-engine TXT-01..09)."""
import re

import pytest

from spinagram import Theme
from spinagram.engine.textfit import BREAK_ON, break_token
from spinagram.text import measure

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
