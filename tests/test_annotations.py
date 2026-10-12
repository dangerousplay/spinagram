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
