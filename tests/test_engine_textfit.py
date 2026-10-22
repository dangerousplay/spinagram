"""Text fitting: token breaks, wrapping, shrink and grow (layout-engine TXT-01..09)."""
import math
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


# fit_blocks: mode x text x box (TXT-04, TXT-05, TXT-06) -------------------------------------------------
BODY = Theme.load("default").font("body", 400, 18)
FIT_TEXTS = [
    ("short", "API", "edge proxy"),
    ("token", "lb-pool-https-8081", "8 members · nginx :8081"),
    ("long", "runner-autoscale-template-large", "three managers spread across two availability zones in one region"),
]
FIT_BOXES = [("roomy", 300, 200), ("narrow", 166, 120), ("short", 230, 48), ("tiny", 90, 30)]


def _specs(title, body):
    from spinagram.engine.textfit import BlockSpec
    return [BlockSpec([title], FONT.with_size(24), 1.15, "#000"), BlockSpec([body], BODY, 1.32, "#333")]


def _fits(res, w, h):
    lines_ok = all(measure(ln, b.font) <= w + 0.5 for b in res.blocks for ln in b.lines)
    return lines_ok and res.height <= h + 0.5


def _fit_scenarios():
    return [pytest.param(mode, t, b, w, h, id=f"{mode}-{tn}-{bn}")
            for mode in ("none", "shrink", "grow", "shrink-then-grow")
            for tn, t, b in FIT_TEXTS for bn, w, h in FIT_BOXES]


@pytest.mark.parametrize("mode,title,body,w,h", _fit_scenarios())
def test_fit_blocks_modes(mode, title, body, w, h):
    from spinagram.engine.textfit import fit_blocks
    res = fit_blocks(_specs(title, body), w, h, mode=mode)
    sizes = [b.font.size for b in res.blocks]
    if mode == "none":                                   # TXT-06: 0.3 behaviour, spaces only, no size change
        assert [b.lines for b in res.blocks] == [wrap(title, FONT.with_size(24), w), wrap(body, BODY, w)]
        assert sizes == [24, 18]
        return
    if res.ok and res.strategy != "grow":
        assert _fits(res, w, h)
    if "shrink" in mode:                                 # TXT-04: 1 px steps, never below 85 %
        assert sizes[0] >= 24 * 0.85 and sizes[1] >= 18 * 0.85
        assert float(24 - sizes[0]).is_integer() and float(18 - sizes[1]).is_integer()
        if res.ok and res.strategy == "shrink":          # first size that fits: one px larger did not
            bigger = fit_blocks(_specs(title, body), w, h, mode="shrink", min_scale=(sizes[0] + 1) / 24)
            assert not bigger.ok or bigger.blocks[0].font.size > sizes[0]
    else:
        assert sizes == [24, 18]                         # grow alone never shrinks
    if res.strategy == "grow" and res.ok:                # TXT-05: box grows to the text height
        assert res.height > h and all(measure(ln, b.font) <= w + 0.5 for b in res.blocks for ln in b.lines)
    if res.strategy == "grow" and not res.ok:            # TXT-07: grow tried last, but no size fits the width
        assert any(measure(ln, b.font) > w + 0.5 for b in res.blocks for ln in b.lines)
    if not res.ok and "shrink" in mode:
        assert sizes == [24 - math.floor(24 - 24 * 0.85), 18 - math.floor(18 - 18 * 0.85)]  # exhausted: 21, 16


def test_fit_blocks_short_text_keeps_base_size():
    from spinagram.engine.textfit import fit_blocks
    res = fit_blocks(_specs("API", "edge"), 300, 200)
    assert (res.ok, res.strategy, [b.font.size for b in res.blocks]) == (True, "wrap", [24, 18])


def test_fit_blocks_token_breaks_before_shrinking():
    from spinagram.engine.textfit import fit_blocks
    res = fit_blocks(_specs("lb-pool-https-8081-backend", "x"), 166, 300)
    assert (res.ok, res.strategy, res.blocks[0].font.size) == (True, "break", 24)


def test_fit_blocks_empty_text_is_noop():                # edge case: empty text
    from spinagram.engine.textfit import fit_blocks
    assert fit_blocks([], 100, 100).ok and fit_blocks([], 100, 100).blocks == []


def test_fit_blocks_narrow_box_terminates():             # edge case: box narrower than one glyph
    from spinagram.engine.textfit import fit_blocks
    res = fit_blocks(_specs("Wide", "words"), 4, 10, mode="shrink-then-grow")
    assert not res.ok and [b.font.size for b in res.blocks] == [21, 16]


def test_fit_blocks_rejects_unknown_mode():
    from spinagram.engine.textfit import fit_blocks
    with pytest.raises(ValueError, match="fit 'squash'"):
        fit_blocks(_specs("a", "b"), 10, 10, mode="squash")


# builder integration (TXT-08 + TXT-01..06 on real nodes) -------------------------------------------------
from spinagram import Diagram, build_scene  # noqa: E402
from spinagram.scene import Shape  # noqa: E402

THEME = Theme.load("default")
NODE_TEXTS = [
    ("hostname", "lb-pool-https-8081", "8 members · nginx :8081"),
    ("cidr-body", "subnet-a", "10.0.0.0/22 · 10.0.8.0/21"),
    ("long-title", "Managers default runner-autoscale", "spread across zones"),
    ("short", "API", None),
]
NODE_KINDS = [("box", {}), ("decision", {}), ("diamond", {})]


def _node_shape(kind, title, text, w=230, h=120, **kw):
    d = Diagram("F", "Fit")
    d.add(kind, title, id="n", x=100, y=100, w=w, h=h, text=text, **kw)
    return next(i for i in build_scene(d, THEME).items if isinstance(i, Shape) and i.id == "n")


@pytest.mark.parametrize("kind,title,text", [
    pytest.param(k, t, b, id=f"{k}-{n}") for k, _ in NODE_KINDS for n, t, b in NODE_TEXTS])
def test_default_fit_keeps_lines_inside_label_box(kind, title, text):
    """Text never leaves the box while a strategy remains; once they are exhausted check reports it."""
    from spinagram.qa import check
    d = Diagram("F", "Fit")
    d.add(kind, title, id="n", x=100, y=100, w=200 if kind != "box" else 230, h=160, text=text)
    sc = build_scene(d, THEME)
    s = next(i for i in sc.items if isinstance(i, Shape) and i.id == "n")
    _, _, w, _ = s.label.box
    outside = [ln for b in s.label.blocks for ln in b.lines if measure(ln, b.font) > w + 0.5]
    reported = [i for i in check(sc) if i.item == "n" and i.kind == "overflow-x"]
    assert len(reported) == len(outside)
    for b in s.label.blocks:
        if any(ln in outside for ln in b.lines):
            assert b.font.size == math.ceil(b.font.size) and b.font.size <= 24 - 3  # shrunk to the floor first


FIT_OPTION_SCENARIOS = [
    ("python-none", {"fit": "none"}, None, 24),
    ("python-shrink-floor", {"fit": "shrink", "min_scale": 0.5}, None, None),
    ("theme-none", {}, {"fit": "none"}, 24),
    ("node-beats-theme", {"fit": "none"}, {"fit": "shrink"}, 24),
]


@pytest.mark.parametrize("node_kw,theme_node,size", [s[1:] for s in FIT_OPTION_SCENARIOS],
                         ids=[s[0] for s in FIT_OPTION_SCENARIOS])
def test_fit_options_from_node_and_theme(tmp_path, node_kw, theme_node, size):  # TXT-08
    th = THEME
    if theme_node:
        import yaml
        (tmp_path / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump({"defaults": {"node": theme_node}}))
        th = Theme.load(tmp_path)
    d = Diagram("F", "Fit")
    d.box("Managers default runner autoscale group", id="n", x=0, y=0, w=200, h=60, **node_kw)
    s = next(i for i in build_scene(d, th).items if isinstance(i, Shape) and i.id == "n")
    got = s.label.blocks[0].font.size
    if size is not None:
        assert got == size
    else:
        assert 12 <= got < 24      # min_scale 0.5 lets the title go below the 0.85 floor (20.4)


def test_fit_options_from_yaml():  # TXT-08 YAML parity
    from spinagram.yaml_io import from_dict
    d = from_dict({"id": "F", "title": "Fit", "nodes": [
        {"id": "n", "title": "x", "x": 0, "y": 0, "w": 100, "h": 50, "fit": "grow", "min_scale": 0.9, "break_on": "-"}]})
    assert {k: d.nodes[0].extra[k] for k in ("fit", "min_scale", "break_on")} == {
        "fit": "grow", "min_scale": 0.9, "break_on": "-"}


def test_grow_makes_the_box_taller():  # TXT-05 on a node
    s = _node_shape("box", "Managers", "three managers spread across two availability zones in one region of the "
                    "cloud with autoscaling", w=230, h=80, fit="grow")
    assert s.h > 80
    assert sum(b.height for b in s.label.blocks) + 10 <= s.label.box[3] + 0.5


OVERFLOW_SCENARIOS = [
    # id, fit, w, h, title, expected kind, expected detail suffix
    ("shrink-x", "shrink", 90, 200, "averyveryverylongunbreakabletokenname", "overflow-x", " after shrink to 21px"),
    ("none-x", "none", 90, 200, "averyveryverylongunbreakabletokenname", "overflow-x", " after wrap to 24px"),
    ("shrink-y", "shrink", 230, 40, "one two three four five six seven eight", "overflow-y", " after shrink to 21px"),
    ("grow-x", "grow", 90, 40, "averyveryverylongunbreakabletokenname", "overflow-x", " after grow to 24px"),
]


@pytest.mark.parametrize("fit,w,h,title,kind,suffix", [s[1:] for s in OVERFLOW_SCENARIOS],
                         ids=[s[0] for s in OVERFLOW_SCENARIOS])
def test_overflow_detail_names_strategy(fit, w, h, title, kind, suffix):  # TXT-07
    from spinagram.qa import check
    d = Diagram("F", "Fit")
    d.box(title, id="n", x=0, y=0, w=w, h=h, fit=fit)
    got = [i for i in check(build_scene(d, THEME)) if i.item == "n" and i.kind == kind]
    assert got and all(i.detail.endswith(suffix) for i in got)


@pytest.mark.parametrize("fit", ["shrink", "grow", "shrink-then-grow"])
def test_no_overflow_when_fitting_succeeds(fit):  # TXT-07: nothing reported when a strategy fits
    from spinagram.qa import check
    d = Diagram("F", "Fit")
    d.box("lb-pool-https-8081", id="n", x=200, y=200, w=166, h=150, text="8 members · nginx :8081", fit=fit)
    assert [i for i in check(build_scene(d, THEME)) if i.item == "n"] == []


TRACKING_SCENARIOS = [
    pytest.param(tr, label, id=f"track{tr}-{len(label)}ch")
    for tr in (0, 0.06, 0.12) for label in ("AZ", "network-a · 10.0.0.0/24", "Availability zone site-a RHEL 9")]


@pytest.mark.parametrize("tracking,label", TRACKING_SCENARIOS)
def test_zone_label_width_includes_letter_spacing(tmp_path, tracking, label):  # TXT-09
    from spinagram.scene import Text
    (tmp_path / "theme.yaml").write_text(f"extends: default\ndefaults: {{zone: {{label_tracking: {tracking}}}}}\n")
    th = Theme.load(tmp_path)
    d = Diagram("Z", "Zone")
    d.zone(label, x=0, y=0, w=900, h=300)
    t = next(i for i in build_scene(d, th).items if isinstance(i, Text) and i.id == "z0-label")
    size = th.defaults("zone").get("label_size", 16)
    assert t.letter_spacing == pytest.approx(tracking * size)
    assert t.width == pytest.approx(measure(label.upper(), t.block.font) + tracking * size * len(label))


# free labels: size, roles, wrapping (TXT-16..18) --------------------------------------------------------------
from spinagram.scene import Text  # noqa: E402


def _label(**kw):
    d = Diagram("L", "Labels")
    d.label(kw.pop("text", "subnet-a network"), x=200, y=300, **kw)
    return next(i for i in build_scene(d, THEME).items if isinstance(i, Text) and i.id not in ("chrome-title",)
                and not i.id.startswith("chrome"))


@pytest.mark.parametrize("size", [12, 20, 28])
def test_label_size(size):  # TXT-16
    assert _label(size=size).block.font.size == size


ROLES = [
    # id, role, expected (upper text, size, weight, letter spacing, colour)
    ("zone-label", "zone-label", ("SUBNET-A NETWORK", 16, 700, 16 * 0.06, THEME.zone_style(None)["label"])),
    ("caption", "caption", ("subnet-a network", 15, 400, 0, THEME.color("text-muted"))),
    ("footnote", "footnote", ("subnet-a network", 13, 400, 0, THEME.color("text-muted"))),
]


@pytest.mark.parametrize("role,expected", [r[1:] for r in ROLES], ids=[r[0] for r in ROLES])
def test_label_roles(role, expected):  # TXT-17
    t = _label(role=role)
    text, size, weight, tracking, colour = expected
    assert (t.block.lines[0], t.block.font.size, t.block.font.weight, t.block.color) == (text, size, weight, colour)
    assert t.letter_spacing == pytest.approx(tracking)


def test_unknown_role_raises():
    with pytest.raises(ValueError, match="label role 'banner'"):
        Diagram("L", "L").label("x", x=0, y=0, role="banner")


@pytest.mark.parametrize("max_width", [120, 200, 400])
def test_label_max_width_wraps(max_width):  # TXT-18
    text = "egress through NAT to the destinations group"
    t = _label(text=text, max_width=max_width)
    assert all(measure(ln, t.block.font) <= max_width for ln in t.block.lines)
    assert " ".join(t.block.lines) == text and (len(t.block.lines) > 1) == (measure(text, t.block.font) > max_width)


def test_label_options_from_yaml():
    from spinagram.yaml_io import from_dict
    d = from_dict({"id": "L", "title": "L", "nodes": [{"id": "l", "kind": "text", "title": "net", "x": 100,
                                                       "y": 100, "size": 22, "role": "caption", "max_width": 300}]})
    assert {k: d.nodes[0].extra[k] for k in ("size", "role", "max_width")} == {"size": 22, "role": "caption",
                                                                              "max_width": 300}


# TXT-08 behaviour (fix after verification): break_on and theme defaults change the result -----------------------
@pytest.mark.parametrize("break_on,lines_have_dot_breaks", [("-./:·", True), ("-", False)], ids=["default", "dash-only"])
def test_break_on_changes_where_tokens_break(break_on, lines_have_dot_breaks):
    d = Diagram("F", "Fit")
    d.box("gitlab.node-a.example.internal", id="n", x=200, y=200, w=200, h=200, break_on=break_on)
    s = next(i for i in build_scene(d, THEME).items if isinstance(i, Shape) and i.id == "n")
    ends = [ln[-1] for ln in s.label.blocks[0].lines[:-1]]
    assert ("." in ends) == lines_have_dot_breaks and all(e in break_on for e in ends)


@pytest.mark.parametrize("theme_node,size", [({"min_scale": 0.5}, 12), ({"min_scale": 0.95}, 23)],
                         ids=["min_scale-0.5", "min_scale-0.95"])
def test_theme_defaults_drive_fitting(tmp_path, theme_node, size):
    import yaml
    (tmp_path / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump({"defaults": {"node": theme_node}}))
    d = Diagram("F", "Fit")
    d.box("averyveryverylongunbreakable-token", id="n", x=200, y=200, w=120, h=200)
    s = next(i for i in build_scene(d, Theme.load(tmp_path)).items if isinstance(i, Shape) and i.id == "n")
    assert s.label.blocks[0].font.size == size


@pytest.mark.parametrize("break_on,dot_breaks", [("-./:·", True), ("-", False)], ids=["default", "theme-dash-only"])
def test_theme_break_on_changes_breaks(tmp_path, break_on, dot_breaks):
    import yaml
    (tmp_path / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump({"defaults": {"node": {"break_on": break_on}}}))
    d = Diagram("F", "Fit")
    d.box("gitlab.node-a.example.internal", id="n", x=200, y=200, w=200, h=200)
    s = next(i for i in build_scene(d, Theme.load(tmp_path)).items if isinstance(i, Shape) and i.id == "n")
    assert ("." in [ln[-1] for ln in s.label.blocks[0].lines[:-1]]) == dot_breaks
