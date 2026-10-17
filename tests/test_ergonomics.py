"""Less boilerplate in Python specs: shared node sizes and diagrams found without a convention variable."""
from __future__ import annotations

import pytest

from spinagram import Diagram, load


def test_size_sets_width_and_height():
    d = Diagram("S", "Size")
    n = d.box("A", size=(230, 84))
    assert (n.w, n.h) == (230, 84)


def test_node_size_applies_to_boxes_created_inside_a_group_and_nests():
    d = Diagram("G", "Groups", node_size=(200, 80))
    top = d.box("Top")
    with d.group("Outer", node_size=(240, 90)):
        outer = d.box("Outer box")
        with d.group("Inner"):  # no size of its own: the outer one still applies
            inner = d.box("Inner box")
        with d.group("Pods", node_size=(150, 60)):
            pod = d.box("Pod")
        own = d.box("Own", w=300, h=100)  # an explicit size always wins
    after = d.box("After")
    assert [(n.w, n.h) for n in (top, outer, inner, pod, own, after)] == [
        (200, 80), (240, 90), (240, 90), (150, 60), (300, 100), (200, 80)]


def test_sized_but_unplaced_nodes_are_laid_out_automatically():
    d = Diagram("A", "Auto", node_size=(200, 80))
    d.box("A") >> d.box("B")
    assert d.auto  # sizes are hints; only positions make a diagram hand-placed


def test_python_spec_without_a_convention_variable(tmp_path):
    (tmp_path / "spec.py").write_text(
        "from spinagram import Diagram\n"
        "first = Diagram('A1', 'First')\nfirst.box('X')\n"
        "second = Diagram('A2', 'Second')\nsecond.box('Y')\n"
        "alias = first\n"          # the same diagram twice: listed once
        "_scratch = Diagram('Z', 'private')\n")
    assert [d.id for d in load(tmp_path / "spec.py")] == ["A1", "A2"]


def test_python_spec_convention_variables_still_win(tmp_path):
    (tmp_path / "spec.py").write_text(
        "from spinagram import Diagram\n"
        "a, b = Diagram('A1', 'A'), Diagram('B1', 'B')\n"
        "diagrams = [b]\n")
    assert [d.id for d in load(tmp_path / "spec.py")] == ["B1"]


def test_python_spec_with_no_diagram_says_so(tmp_path):
    (tmp_path / "empty.py").write_text("x = 1\n")
    with pytest.raises(ValueError, match="no diagram found"):
        load(tmp_path / "empty.py")


def test_node_size_leaves_markers_and_decisions_alone():
    from spinagram import Activity, Flowchart

    act = Activity("AC", "Activity", node_size=(168, 62))
    with act.sequence():
        start = act.start()
        step = act.action("Build")
        end = act.end()
    assert (step.w, step.h) == (168, 62) and (start.w, start.h) != (168, 62) and (end.w, end.h) != (168, 62)
    fc = Flowchart("FC", "Flow", node_size=(200, 80))
    begin, check, work = fc.start(), fc.decision("OK?"), fc.process("Work")
    assert (work.w, work.h) == (200, 80)
    assert (begin.w, begin.h) != (200, 80) and (check.w, check.h) != (200, 80)
