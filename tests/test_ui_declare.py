"""Where an element of the styles report is declared in its spec (features/inspector-declarations)."""
from __future__ import annotations

from spinagram.ui.declare import locate

YAML = """\
id: L01
title: Vault and Consul
groups:
  - id: region
    label: us-east-1
    children: [users, alb]
  - {label: Shared, children: [s3]}
nodes:
  - {id: users, title: Applications, text: "Kubernetes"}
  - {id: alb, title: ALB}
  - id: "vault.1"
    title: Vault
  - {title: "Uploads"}
edges:
  - "users -> alb: HTTPS"
  - {from: alb, to: vault.1}
"""

PY = """\
from spinagram import Diagram

d = Diagram("Q01", "Web app")
users = d.box("Users", icon="aws:users")
with d.group("us-east-1", id="region"):
    lb = d.box("Load balancer", id='lb')
    api = d.box(["Order", "API"])
users.to(lb, "HTTPS") >> api
"""


def node(id, label=None):
    return {"type": "node", "id": id, "attrs": {"label": label} if label else {}}


def group(id, label=None):
    return {"type": "group", "id": id, "attrs": {"label": label} if label else {}}


def edge(src, dst, label=None):
    attrs = {"from": src, "to": dst}
    if label:
        attrs["label"] = label
    return {"type": "edge", "id": None, "attrs": attrs}


def test_yaml_node_and_group_by_id():  # DECL-01
    assert locate(YAML, ".yaml", node("users", "Applications")) == 9
    assert locate(YAML, ".yaml", node("alb", "ALB")) == 10
    assert locate(YAML, ".yml", group("region", "us-east-1")) == 4


def test_yaml_id_is_literal_and_word_bounded():  # DECL-01, edge case: regex characters
    assert locate(YAML, ".yaml", node("vault.1", "Vault")) == 11      # quoted id, `.` matched literally
    assert locate(YAML, ".yaml", node("vaultx1", "nope")) is None      # `.` is not a wildcard
    assert locate(YAML, ".yaml", node("user", "nope")) is None         # `users` does not hold `user`


def test_yaml_falls_back_to_title_or_label():  # DECL-01
    assert locate(YAML, ".yaml", node("uploads", "Uploads")) == 13
    assert locate(YAML, ".yaml", group("shared", "Shared")) == 7


def test_python_node_and_group():  # DECL-02
    assert locate(PY, ".py", node("users", "Users")) == 4               # title as a quoted string
    assert locate(PY, ".py", node("lb", "Load balancer")) == 6          # id='lb' wins over the title
    assert locate(PY, ".py", group("region", "us-east-1")) == 5         # id="region"


def test_python_list_title_uses_joined_label():  # edge case: list title
    assert locate('a = d.box("Order API")\n', ".py", node("order-api", "Order API")) == 1


def test_yaml_edges():  # DECL-03
    assert locate(YAML, ".yaml", edge("users", "alb", "HTTPS")) == 15
    assert locate(YAML, ".yaml", edge("alb", "vault.1")) == 16
    assert locate(YAML, ".yaml", edge("alb", "users")) is None          # direction matters


def test_python_edge_by_label():  # DECL-04
    assert locate(PY, ".py", edge("users", "lb", "HTTPS")) == 8
    assert locate(PY, ".py", edge("lb", "api")) is None                 # no label: not found


def test_not_found():  # DECL-05
    assert locate(YAML, ".yaml", node("nowhere", "Nowhere")) is None
    assert locate(PY, ".py", node("nowhere", "Nowhere")) is None
    assert locate("", ".py", node("users", "Users")) is None


def test_diagram_element():  # DECL-06 (diagram)
    assert locate(YAML, ".yaml", {"type": "diagram", "id": "L01", "attrs": {}}) == 1
    assert locate(PY, ".py", {"type": "diagram", "id": "Q01", "attrs": {}}) == 3


# verifier gaps (validation.md, iteration 1) -----------------------------------------------------
def test_yaml_edge_ends_quoted_differently():  # DECL-03 (gap D1)
    assert locate('edges:\n  - {from: a, to: "b"}\n', ".yaml", edge("a", "b")) == 2
    assert locate("edges:\n  - {from: \"a\", to: b}\n", ".yaml", edge("a", "b")) == 2
    assert locate("edges:\n  - {from: 'a', to: \"b\"}\n", ".yaml", edge("a", "b")) == 2


def test_first_match_wins():  # DECL-01, DECL-02, DECL-03: "first" line
    assert locate("- {id: a}\n- {id: a}\n", ".yaml", node("a")) == 1
    assert locate('x = d.box("A")\ny = d.box("A")\n', ".py", node("a", "A")) == 1
    assert locate('- "a -> b"\n- "a -> b"\n', ".yaml", edge("a", "b")) == 1


def test_ids_are_matched_literally():  # DECL-01 edge case: regex characters
    src = "- {id: vaultx1}\n- {id: vault.1}\n"
    assert locate(src, ".yaml", node("vault.1")) == 2                  # `.` would also match the `x` on line 1


def test_yaml_edge_is_word_bounded_on_the_left():  # DECL-03: word-bounded
    assert locate('- "xa -> b"\n- "a -> b"\n', ".yaml", edge("a", "b")) == 2
