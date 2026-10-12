"""Annotations: legends, numbered steps, callouts and note variants (spec: .specs/features/annotations/spec.md)."""
from __future__ import annotations

import pytest

from spinagram import Diagram


def _flow():
    d = Diagram("A1", "Flow")
    users, api, db = d.box("Users"), d.box("API"), d.box("DB")
    e1 = d.edge(users, api, "HTTPS")
    e2 = d.edge(api, db)
    return d, users, api, db, e1, e2


# T1 · model ------------------------------------------------------------------------------------------
def test_steps_number_in_call_order_and_keep_explicit_numbers():  # ANN-15
    d, users, api, db, e1, e2 = _flow()
    d.step("Users call the API", on=e1)
    d.step("The API reads the DB", on=e2)
    d.step("Retry", on=api, n=7)
    d.step("After seven", on=db)
    assert [(s.n, s.text) for s in d.annotations.steps] == [
        (1, "Users call the API"), (2, "The API reads the DB"), (7, "Retry"), (8, "After seven")]


def test_step_targets_edge_node_id_and_pair():  # ANN-13, ANN-14
    d, users, api, db, e1, e2 = _flow()
    d.step("edge", on=e2)
    d.step("node", on=api)
    d.step("id", on="db")
    d.step("pair", on=(users, api))
    d.step("pair of ids", on=("api", "db"))
    got = [(s.edge, s.node) for s in d.annotations.steps]
    assert got == [(1, None), (None, "api"), (None, "db"), (0, None), (1, None)]


def test_edge_step_and_to_step_shortcuts():  # ANN-13
    d, users, api, db, e1, e2 = _flow()
    e2.step("reads")
    users.to(db, "direct", step="bypass")
    assert [(s.n, s.text, s.edge) for s in d.annotations.steps] == [(1, "reads", 1), (2, "bypass", 2)]


def test_step_on_unknown_reference_fails():  # ANN-19 (Python side)
    d, *_ = _flow()
    with pytest.raises(ValueError, match="no edge from 'db' to 'users'"):
        d.step("x", on=("db", "users"))
    with pytest.raises(ValueError, match="unknown node 'ghost'"):
        d.step("x", on="ghost")


def test_legend_items_keep_order_and_labels():  # ANN-02
    d, *_ = _flow()
    d.add_legend({".security": "Security control", "edge.async": "Async event"}, title="Key", position="bottom")
    lg = d.annotations.legend
    assert (lg.title, lg.position, list(lg.items.items())) == (
        "Key", "bottom", [(".security", "Security control"), ("edge.async", "Async event")])
    d.add_legend()
    assert d.annotations.legend.items is None and d.annotations.legend.title == "Legend"


def test_legend_position_is_validated():
    d, *_ = _flow()
    with pytest.raises(ValueError, match="right, bottom"):
        d.add_legend(position="left")


def test_callout_records_target_and_options():  # ANN-20
    d, users, api, *_ = _flow()
    c = d.callout(api, "Rate limited at 1k rps", title="Throttle", kind="warning", side="right", class_="hot")
    assert (c.target, c.text, c.title, c.kind, c.side, c.cls) == ("api", "Rate limited at 1k rps", "Throttle",
                                                                 "warning", "right", "hot")
    assert d.callout("users", "by id").target == "users"


def test_callout_kind_side_and_target_are_validated():  # ANN-25, edge case "another diagram"
    d, users, *_ = _flow()
    with pytest.raises(ValueError, match="info, tip, warning, risk"):
        d.callout(users, "x", kind="danger")
    with pytest.raises(ValueError, match="auto, top, right, bottom, left"):
        d.callout(users, "x", side="middle")
    other = Diagram("B1", "Other")
    stranger = other.box("Stranger")
    with pytest.raises(ValueError, match="'stranger' is not in diagram A1"):
        d.callout(stranger, "x")


def test_note_variants_are_validated():  # ANN-29
    d = Diagram("N1", "Notes")
    assert d.note("Why", text="because", variant="card").extra["variant"] == "card"
    assert "variant" not in d.note("Plain").extra
    with pytest.raises(ValueError, match="sticky, card, quote"):
        d.note("Bad", variant="banner")


# T2 · YAML -------------------------------------------------------------------------------------------
SPEC = """id: Y1
title: Flow
nodes:
  - {id: users, title: Users}
  - {id: api, title: API}
  - {id: db, title: DB}
  - {id: why, kind: note, variant: quote, title: Why}
edges: ["users -> api: HTTPS", "api.bottom -> db.top"]
annotations:
  legend: {title: Key, position: bottom, items: {".hot": Hot path}}
  steps:
    - {on: "users -> api", text: Users call the API}
    - {on: "api -> db", text: The API reads}
    - {on: db, n: 9, text: Stored}
  callouts:
    - {on: db, text: Nightly backup, title: Backup, kind: tip, side: left, class: quiet}
"""


def _load(tmp_path, text):
    from spinagram.yaml_io import load

    (tmp_path / "s.yaml").write_text(text)
    return load(tmp_path / "s.yaml")[0]


def test_yaml_annotations_load(tmp_path):  # ANN-19, ANN-02, ANN-29
    d = _load(tmp_path, SPEC)
    a = d.annotations
    assert (a.legend.title, a.legend.position, a.legend.items) == ("Key", "bottom", {".hot": "Hot path"})
    assert [(s.n, s.text, s.edge, s.node) for s in a.steps] == [
        (1, "Users call the API", 0, None), (2, "The API reads", 1, None), (9, "Stored", None, "db")]
    c = a.callouts[0]
    assert (c.target, c.text, c.title, c.kind, c.side, c.cls) == ("db", "Nightly backup", "Backup", "tip", "left",
                                                                 "quiet")
    assert d.node("why").extra["variant"] == "quote"


@pytest.mark.parametrize("bad, message", [
    ('    - {on: "db -> users", text: x}\n', "no edge from 'db' to 'users'"),
    ("    - {on: ghost, text: x}\n", "unknown node 'ghost'"),
])
def test_yaml_step_reference_must_exist(tmp_path, bad, message):  # ANN-19
    text = SPEC.replace('    - {on: db, n: 9, text: Stored}\n', bad)
    with pytest.raises(ValueError, match=message):
        _load(tmp_path, text)


def test_yaml_invalid_variant_and_kind(tmp_path):  # ANN-29, ANN-25
    with pytest.raises(ValueError, match="sticky, card, quote"):
        _load(tmp_path, SPEC.replace("variant: quote", "variant: banner"))
    with pytest.raises(ValueError, match="info, tip, warning, risk"):
        _load(tmp_path, SPEC.replace("kind: tip", "kind: danger"))


def test_yaml_annotations_round_trip(tmp_path):
    from spinagram.yaml_io import dump, from_dict

    d = _load(tmp_path, SPEC)
    again = from_dict(dump(d))
    assert again.annotations == d.annotations
    assert again.node("why").extra["variant"] == "quote"


# T4 · CSS -------------------------------------------------------------------------------------------
ANN_CSS = """
legend { fill: #111827; stroke: #374151; border-radius: 4; box-shadow: 0 4px 8px #000000 }
legend::title { color: #F9FAFB }
step { fill: #7C3AED; stroke: #4C1D95 }
step::label { color: #FFFFFF }
callout.warning { fill: #FEF3C7; stroke: #B45309 }
callout::title { color: #78350F }
callout::body { color: #92400E }
note.card { stroke: #0EA5E9 }
note.sticky { fill: #FEF9C3 }
"""


def _styled():
    from spinagram.theme import Theme

    d, users, api, db, e1, e2 = _flow()
    d.add_legend()
    d.step("one", on=e1)
    d.step("two", on=e2)
    d.callout(api, "careful", kind="warning")
    d.callout(db, "fine", kind="tip")
    d.note("Card", variant="card")
    d.note("Plain")
    d.css = ANN_CSS
    return d, Theme.load("default")


def test_css_targets_legend_steps_callouts_and_notes():  # ANN-31..34
    from spinagram import css

    d, theme = _styled()
    comp, warnings = css.styles(d, theme)
    assert not warnings
    assert comp["legend"][""]["fill"] == "#111827" and comp["legend"][""]["border-radius"] == 4
    assert comp["legend"]["title"]["color"] == "#F9FAFB"
    for i in (0, 1):
        assert comp[f"step:{i}"][""]["fill"] == "#7C3AED" and comp[f"step:{i}"]["label"]["color"] == "#FFFFFF"
    assert comp["callout:0"][""]["fill"] == "#FEF3C7" and comp["callout:0"]["body"]["color"] == "#92400E"
    assert "fill" not in comp["callout:1"].get("", {})  # .tip, not .warning
    assert comp["callout:1"]["title"]["color"] == "#78350F"
    assert comp["node:card"][""]["stroke"] == "#0EA5E9"
    assert comp["node:plain"][""]["fill"] == "#FEF9C3"


def test_selectors_and_inspector_list_annotations():  # ANN-35
    from spinagram import css

    d, theme = _styled()
    assert css.select(d, "legend") == ["legend"]
    assert css.select(d, "step") == ["step:0", "step:1"]
    assert css.select(d, "callout.warning") == ["callout:0"]
    report = css.inspect(d, theme)
    legend = next(e for e in report["elements"] if e["key"] == "legend")
    assert legend["type"] == "legend" and legend["trace"][""]["decls"][0]["selector"] == "legend"


def test_callout_inline_css_alone_turns_styling_on():
    from spinagram import css
    from spinagram.theme import Theme

    d, users, *_ = _flow()
    d.callout(users, "x", css="fill: #ABCDEF")
    comp, _ = css.styles(d, Theme.load("default"))
    assert comp["callout:0"][""]["fill"] == "#ABCDEF"


# T5 · legend entries and band ----------------------------------------------------------------------
def _classy():
    d = Diagram("L1", "Legend")
    a = d.box("A", class_="web edge-svc")
    b = d.box("B", style="dark")
    c = d.box("C", class_="web", style="default")
    d.box("D", icon="aws:s3")
    d.edge(a, b, class_="async")
    d.edge(b, c, class_="async replication")
    return d


def test_auto_legend_lists_classes_and_styles_once_in_first_use_order():  # ANN-01
    from spinagram.annotate import legend_entries

    d = _classy()
    d.add_legend()
    got = [(e.key, e.label, e.kind, e.ref) for e in legend_entries(d)]
    assert got == [(".web", "Web", "node", "node:a"), (".edge-svc", "Edge svc", "node", "node:a"),
                   ("style:dark", "Dark", "style", "node:b"),
                   ("edge.async", "Async", "edge", "edge:0"), ("edge.replication", "Replication", "edge", "edge:1")]


def test_explicit_legend_keeps_order_labels_and_flags_unused():  # ANN-02, ANN-03, ANN-06
    from spinagram.annotate import legend_entries

    d = _classy()
    d.add_legend({"edge.async": "Async event", "aws:s3": "Object storage", ".ghost": "Nothing",
                  "node.web": "Web tier", "style:dark": "Engine", "gcp:gke": "Unused icon"})
    got = [(e.key, e.label, e.kind, e.ref, e.used) for e in legend_entries(d)]
    assert got == [("edge.async", "Async event", "edge", "edge:0", True),
                   ("aws:s3", "Object storage", "icon", "node:d", True),
                   (".ghost", "Nothing", "node", None, False),
                   ("node.web", "Web tier", "node", "node:a", True),
                   ("style:dark", "Engine", "style", "node:b", True),
                   ("gcp:gke", "Unused icon", "icon", None, False)]


def test_band_reserves_the_right_or_bottom_edge():  # ANN-10
    from spinagram.annotate import band
    from spinagram.theme import Theme

    t = Theme.load("default")
    d = _classy()
    assert band(d, t, 1760) is None
    d.add_legend()
    assert band(d, t, 1760) == ("right", 392)
    d.add_legend(position="bottom")
    side, small = band(d, t, 1760)
    assert side == "bottom" and 0 < small < 400
    for i in range(12):
        d.box(f"N{i}", class_=f"extra-class-{i}")
    assert band(d, t, 1760)[1] > small  # more entries, more rows


def test_steps_alone_take_a_right_band():  # edge case: steps without legend
    from spinagram.annotate import band
    from spinagram.theme import Theme

    d = _classy()
    d.step("go", on="a")
    assert band(d, Theme.load("default"), 1760) == ("right", 392)


# T6 · layout area -----------------------------------------------------------------------------------
def _wide():
    d = Diagram("W1", "Wide", layout={"engine": "flex", "direction": "right"})
    prev = None
    for i in range(4):
        n = d.box(f"Node {i}", class_="tier")
        if prev:
            prev >> n
        prev = n
    return d


def test_right_band_shrinks_the_layout_area():  # ANN-08
    from spinagram.autolayout import _area, apply_layout
    from spinagram.theme import Theme

    t = Theme.load("default")
    d = _wide()
    x, y, w, h = _area(d, t)
    d.add_legend()
    assert _area(d, t) == (x, y, w - 392, h)
    laid = apply_layout(d, t)
    assert max(n.x + n.w for n in laid.nodes) <= x + w - 392 + 0.5


def test_bottom_band_shrinks_the_layout_height():  # ANN-09
    from spinagram.annotate import band
    from spinagram.autolayout import _area
    from spinagram.theme import Theme

    t = Theme.load("default")
    d = _wide()
    x, y, w, h = _area(d, t)
    d.add_legend(position="bottom")
    thickness = band(d, t, w)[1]
    assert _area(d, t) == (x, y, w, h - thickness)


def test_full_area_ignores_the_band():
    from spinagram.autolayout import _area
    from spinagram.theme import Theme

    t = Theme.load("default")
    d = _wide()
    before = _area(d, t)
    d.add_legend()
    assert _area(d, t, reserve=False) == before


# T7 · panels ---------------------------------------------------------------------------------------
PANEL_CSS = """
.hot { fill: #FEE2E2; stroke: #DC2626; stroke-width: 4; stroke-dasharray: 6 3; border-radius: 6 }
edge.async { stroke: #F59E0B; stroke-width: 2; stroke-dasharray: 5 4; marker-start: circle; marker-end: open-arrow }
"""


def _parts(d, monkeypatch=None, icon=None):
    """Laid-out builder, node shapes and edge connectors, and an annotator over them."""
    from spinagram.annotate import Annotator
    from spinagram.autolayout import apply_layout
    from spinagram.layout import _Builder
    from spinagram.theme import Theme

    t = Theme.load("default")
    if monkeypatch is not None and icon is not None:
        real = Theme.icon
        monkeypatch.setattr(Theme, "icon", lambda self, ref, *a, **k: icon if ref == "aws:s3" else real(self, ref, *a, **k))
    laid = apply_layout(d, t)
    b = _Builder(laid, t)
    shapes = {n.id: b.node(n) for n in laid.nodes}
    conns = [b.edge(i, e) for i, e in enumerate(laid.edges)]
    return b, shapes, conns, Annotator(b), t


def _panel_diagram():
    d = Diagram("P1", "Panels", layout={"engine": "flex", "direction": "right"})
    d.css = PANEL_CSS
    a = d.box("A", class_="hot")
    b = d.box("B")
    c = d.box("C", icon="aws:s3")
    d.edge(a, b, class_="async")
    d.edge(b, c)
    return d


def _by_id(items):
    return {getattr(i, "id", None): i for i in items}


def test_legend_node_swatch_copies_the_computed_node_style(monkeypatch, tmp_path):  # ANN-04
    d = _panel_diagram()
    d.add_legend({".hot": "Hot path"})
    b, shapes, conns, ann, t = _parts(d)
    sw = _by_id(ann.panels(conns))["legend-0-swatch"]
    node = shapes["a"]
    assert (sw.fill, sw.stroke, sw.stroke_width, sw.dash, sw.dashed) == ("#FEE2E2", "#DC2626", 4, node.dash, True)
    assert sw.radius == pytest.approx(6 * sw.h / node.h)
    assert node.dash == [6.0, 3.0]


def test_legend_edge_sample_copies_the_computed_edge_style():  # ANN-05
    d = _panel_diagram()
    d.add_legend({"edge.async": "Async"})
    b, shapes, conns, ann, t = _parts(d)
    sample = _by_id(ann.panels(conns))["legend-0-sample"]
    e = conns[0]
    assert (sample.color, sample.width, sample.dash, sample.marker_start, sample.marker_end) == (
        "#F59E0B", 2, [5.0, 4.0], "circle", "open-arrow")
    assert (sample.arrow_start, sample.arrow_end) == (e.arrow_start, e.arrow_end) == (True, True)
    (x1, y1), (x2, y2) = sample.points
    assert y1 == y2 and x2 > x1


def test_legend_icon_entry_shows_the_icon(monkeypatch, tmp_path):  # ANN-06
    icon = tmp_path / "s3.svg"
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><rect width="8" height="8"/></svg>')
    d = _panel_diagram()
    d.add_legend({"aws:s3": "Object storage"})
    b, shapes, conns, ann, t = _parts(d, monkeypatch, icon)
    sw = _by_id(ann.panels(conns))["legend-0-swatch"]
    assert sw.icon is not None and sw.icon.path == icon and sw.fill is None


def test_legend_is_a_titled_card_in_the_right_band():  # ANN-07
    from spinagram.autolayout import _area

    d = _panel_diagram()
    d.add_legend({".hot": "Hot path", "edge.async": "Async"})
    b, shapes, conns, ann, t = _parts(d)
    items = _by_id(ann.panels(conns))
    card, title = items["legend"], items["legend-title"]
    ax, ay, aw, ah = _area(d, t, reserve=False)
    assert (card.x, card.y, card.w) == (ax + aw - 360, ay, 360)
    assert title.block.lines == ["Legend"] and card.x < title.x < card.x + card.w
    assert items["legend-1-label"].block.lines == ["Async"]


def test_steps_panel_lists_steps_in_ascending_order():  # ANN-17
    d = _panel_diagram()
    d.step("Second thing", on=("b", "c"), n=2)
    d.step("First thing", on=("a", "b"), n=1)
    d.step("Last thing", on="c", n=7)
    b, shapes, conns, ann, t = _parts(d)
    items = _by_id(ann.panels(conns))
    assert items["steps-title"].block.lines == ["Steps"]
    rows = sorted((items[f"steps-{k}-text"].y, items[f"steps-{k}-badge"].label.blocks[0].lines[0],
                   " ".join(items[f"steps-{k}-text"].block.lines)) for k in range(3))
    assert [(n, text) for _, n, text in rows] == [("1", "First thing"), ("2", "Second thing"), ("7", "Last thing")]


def test_steps_panel_sits_below_the_legend():
    d = _panel_diagram()
    d.add_legend()
    d.step("go", on="a")
    b, shapes, conns, ann, t = _parts(d)
    items = _by_id(ann.panels(conns))
    assert items["steps"].y >= items["legend"].y + items["legend"].h and items["steps"].x == items["legend"].x


# T8 · step badges -----------------------------------------------------------------------------------
def _badge_diagram():
    d = Diagram("S1", "Steps", layout={"engine": "flex", "direction": "right"})
    a, b, c = d.box("A"), d.box("B"), d.box("C")
    d.edge(a, b, "HTTPS")
    d.edge(b, c)
    d.step("labelled", on=("a", "b"))
    d.step("plain", on=("b", "c"))
    d.step("node", on="c")
    return d


def _overlap(r, s):
    return r[0] < s[0] + s[2] and s[0] < r[0] + r[2] and r[1] < s[1] + s[3] and s[1] < r[1] + r[3]


def test_badge_sits_beside_the_edge_label():  # ANN-13, ANN-18
    b, shapes, conns, ann, t = _parts(_badge_diagram())
    badge = _by_id(ann.badges(conns))["step-0-badge"]
    lab = conns[0].label
    assert badge.x + badge.w <= lab.x  # before the label, clear of the arrowhead
    assert abs((badge.y + badge.h / 2) - (lab.y + lab.h / 2)) < 0.5
    assert not _overlap((badge.x, badge.y, badge.w, badge.h), (lab.x, lab.y, lab.w, lab.h))
    assert badge.label.blocks[0].lines == ["1"]


def test_badge_on_an_unlabelled_edge_sits_at_its_midpoint():  # ANN-13
    b, shapes, conns, ann, t = _parts(_badge_diagram())
    badge = _by_id(ann.badges(conns))["step-1-badge"]
    pts = conns[1].points
    seg = [((x1 + x2) / 2, (y1 + y2) / 2, ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
           for (x1, y1), (x2, y2) in zip(pts, pts[1:])]
    assert len(seg) == 1  # flex without route: a straight edge
    mx, my = seg[0][0], seg[0][1]
    assert (round(badge.x + badge.w / 2, 1), round(badge.y + badge.h / 2, 1)) == (round(mx, 1), round(my, 1))
    assert badge.label.blocks[0].lines == ["2"]


def test_node_badge_is_centred_on_the_top_left_corner():  # ANN-14
    b, shapes, conns, ann, t = _parts(_badge_diagram())
    badge = _by_id(ann.badges(conns))["step-2-badge"]
    node = shapes["c"]
    assert (badge.x + badge.w / 2, badge.y + badge.h / 2) == (node.x, node.y)


def test_panel_badges_match_diagram_badges():  # ANN-17
    b, shapes, conns, ann, t = _parts(_badge_diagram())
    on_edges = _by_id(ann.badges(conns))
    panel = _by_id(ann.panels(conns))
    for k in range(3):
        a_, p = on_edges[f"step-{k}-badge"], panel[f"steps-{k}-badge"]
        assert (a_.w, a_.h, a_.fill, a_.stroke, a_.radius, a_.label.blocks[0].lines) == (
            p.w, p.h, p.fill, p.stroke, p.radius, p.label.blocks[0].lines)


def test_badge_on_a_bent_edge_sits_halfway_along_it():  # ANN-13
    from spinagram.annotate import Annotator

    assert Annotator._midpoint([(0, 0), (100, 0), (100, 50)]) == (75, 0)
    assert Annotator._midpoint([(0, 0), (0, 40), (60, 40)]) == (10, 40)


# T9 · callouts -------------------------------------------------------------------------------------
def _target(*blockers):
    """A target box in the middle of the canvas and boxes blocking the given sides."""
    d = Diagram("C1", "Callouts")
    d.box("Target", x=860, y=520, w=200, h=100)
    spots = {"top": (860, 380, 200, 120), "right": (1200, 470, 300, 200), "bottom": (860, 690, 200, 120),
             "left": (420, 470, 300, 200)}
    for side in blockers:
        x, y, w, h = spots[side]
        d.box(f"Block {side}", x=x, y=y, w=w, h=h)
    return d


def _callout_items(d):
    b, shapes, conns, ann, t = _parts(d)
    items = ann.callouts([s for s in shapes.values()])
    return _by_id(items), shapes, ann, t


def _side(bubble, node):
    if bubble.y + bubble.h <= node.y:
        return "top"
    if bubble.x >= node.x + node.w:
        return "right"
    if bubble.y >= node.y + node.h:
        return "bottom"
    if bubble.x + bubble.w <= node.x:
        return "left"
    return "overlapping"


def test_callout_draws_a_bubble_and_a_leader_to_the_node():  # ANN-20
    d = _target()
    d.callout("target", "Snapshots every six hours", title="Backups")
    items, shapes, ann, t = _callout_items(d)
    bubble, leader, node = items["callout-0"], items["callout-0-leader"], shapes["target"]
    texts = [" ".join(blk.lines) for blk in bubble.label.blocks]
    assert texts == ["Backups", "Snapshots every six hours"]
    (_, y1), (x2, y2) = leader.points[0], leader.points[-1]
    assert bubble.y + bubble.h == y1 and node.y == y2 and node.x <= x2 <= node.x + node.w  # top side
    assert leader.marker_end == "circle"


@pytest.mark.parametrize("kind, token, glyph", [("info", "primary", "i"), ("tip", "success", "+"),
                                                ("warning", "warning", "!"), ("risk", "alert", "×")])
def test_callout_kind_sets_colour_and_glyph(kind, token, glyph):  # ANN-21
    d = _target()
    d.callout("target", "x", kind=kind)
    items, shapes, ann, t = _callout_items(d)
    assert items["callout-0"].stroke == t.color(token)
    assert items["callout-0-glyph"].fill == t.color(token)
    assert items["callout-0-glyph"].label.blocks[0].lines == [glyph]


@pytest.mark.parametrize("blocked, expected", [((), "top"), (("top",), "right"), (("top", "right"), "bottom"),
                                               (("top", "right", "bottom"), "left")])
def test_auto_side_takes_the_first_free_side(blocked, expected):  # ANN-22
    d = _target(*blocked)
    d.callout("target", "note")
    items, shapes, ann, t = _callout_items(d)
    bubble = items["callout-0"]
    assert _side(bubble, shapes["target"]) == expected
    for s in shapes.values():
        assert s.id == "target" or not _overlap((bubble.x, bubble.y, bubble.w, bubble.h), (s.x, s.y, s.w, s.h))
    assert ann.issues == []


def test_auto_side_avoids_earlier_callouts():  # ANN-22
    d = _target()
    d.callout("target", "first")
    d.callout("target", "second")
    items, shapes, ann, t = _callout_items(d)
    assert (_side(items["callout-0"], shapes["target"]), _side(items["callout-1"], shapes["target"])) == (
        "top", "right")


def test_explicit_side_is_honoured():  # ANN-23
    d = _target()
    d.callout("target", "note", side="left")
    items, shapes, ann, t = _callout_items(d)
    assert _side(items["callout-0"], shapes["target"]) == "left"


def test_no_free_side_falls_back_to_top_and_reports():  # ANN-24
    d = _target("top", "right", "bottom", "left")
    d.callout("target", "crowded")
    items, shapes, ann, t = _callout_items(d)
    assert _side(items["callout-0"], shapes["target"]) == "top"
    assert ann.issues == [("callout-0", "overlap", "no free side around 'target'; placed on top")]


# T10 · scene integration ---------------------------------------------------------------------------
def _annotated():
    d = Diagram("I1", "Integrated", subtitle="every annotation", layout={"engine": "flex", "direction": "right"})
    users, api, db = d.box("Users", class_="ext"), d.box("API", class_="svc"), d.box("DB", class_="store")
    users.to(api, "HTTPS", step="Users call the API")
    api.to(db, step="The API reads", class_="async")
    d.add_legend()
    d.callout(db, "Encrypted at rest", kind="tip")
    d.note("Why", text="Explain the choice", variant="card")
    return d


def test_scene_contains_badges_panels_and_callouts():  # ANN-07, ANN-13, ANN-20
    from spinagram.layout import build_scene
    from spinagram.theme import Theme

    sc = build_scene(_annotated(), Theme.load("default"))
    ids = [getattr(i, "id", None) for i in sc.items]
    for want in ("step-0-badge", "step-1-badge", "legend", "legend-title", "steps", "steps-0-badge", "callout-0",
                 "callout-0-leader", "callout-0-glyph"):
        assert want in ids, want
    # z-order: badges after edges, callouts after panels, chrome title last of the content
    assert ids.index("step-0-badge") > ids.index("e1") and ids.index("callout-0") > ids.index("steps")


def test_unannotated_scene_has_no_annotation_items():
    from spinagram.layout import build_scene
    from spinagram.theme import Theme

    d = Diagram("I2", "Plain", layout={"engine": "flex"})
    d.box("A") >> d.box("B")
    ids = [getattr(i, "id", "") or "" for i in build_scene(d, Theme.load("default")).items]
    assert not [i for i in ids if i.startswith(("legend", "steps", "step-", "callout"))]


def test_annotated_svg_renders():
    from spinagram.backends.svg import to_svg
    from spinagram.layout import build_scene
    from spinagram.theme import Theme

    svg = to_svg(build_scene(_annotated(), Theme.load("default")))
    assert ">Legend<" in svg and ">Steps<" in svg and ">Encrypted at rest<" in svg and ">Users call the API<" in svg


# T11 · note variants -------------------------------------------------------------------------------
def _notes(monkeypatch=None, icon=None):
    from spinagram.layout import build_scene
    from spinagram.theme import Theme

    t = Theme.load("default")
    if monkeypatch is not None:
        monkeypatch.setattr(Theme, "icon", lambda self, ref, *a, **k: icon if ref == "aws:s3" else None)
    d = Diagram("V1", "Notes")
    d.note("Sticky", text="as before", x=100, y=300, w=400, h=200)
    d.note("Card", text="with a bar", variant="card", x=600, y=300, w=400, h=200, icon="aws:s3")
    d.note("Quote", text="Simplicity is prerequisite for reliability.", variant="quote", x=1100, y=300, w=500,
           h=200)
    return _by_id(build_scene(d, t).items), t


def test_card_note_has_a_primary_accent_bar(monkeypatch, tmp_path):  # ANN-26, ANN-30
    icon = tmp_path / "s3.svg"
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><rect width="8" height="8"/></svg>')
    items, t = _notes(monkeypatch, icon)
    card, bar = items["card"], items["card-accent"]
    assert (bar.x, bar.w, bar.fill) == (card.x, 6, t.color("primary"))
    assert card.y < bar.y and bar.y + bar.h < card.y + card.h and bar.h >= card.h / 2  # inset from the corners
    assert card.fill == t.color(t.get("canvas", "background")) and card.shadow is not None
    assert card.icon is not None and card.icon.path == icon


def test_quote_note_has_a_quote_mark_and_italic_body():  # ANN-27
    items, t = _notes()
    quote, mark = items["quote"], items["quote-mark"]
    assert mark.block.lines == ["“"] and mark.block.color == t.color("primary")
    assert quote.x < mark.x < quote.label.box[0]
    body, attribution = quote.label.blocks
    assert body.font.italic and body.lines[0].startswith("Simplicity")
    assert attribution.lines == ["— Quote"] and not attribution.font.italic


def test_sticky_note_is_unchanged():  # ANN-28
    items, t = _notes()
    s = items["sticky"]
    nd, st = t.defaults("node"), t.node_style(None)
    assert (s.fill, s.stroke, s.stroke_width, s.radius, s.shadow) == (
        st["fill"], st["stroke"], nd["note_stroke_width"], nd["radius"], None)
    assert "sticky-accent" not in items and "sticky-mark" not in items
    assert not any(b.font.italic for b in s.label.blocks)
