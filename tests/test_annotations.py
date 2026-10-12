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
