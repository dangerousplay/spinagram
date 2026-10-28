"""Zone and node ids never collide: a zone whose id was a node id inside it made zone placement loop forever.

Every build runs in a subprocess with a timeout, so a regression fails instead of hanging the suite.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from spinagram import Diagram
from spinagram.yaml_io import from_dict

TIMEOUT = 60  # s: a build takes well under a second; the old loop never ended


def _run(code: str) -> str:
    """Run ``code`` in a fresh interpreter; returns its stdout (the test fails on a timeout or an error)."""
    try:
        done = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], capture_output=True, text=True,
                              timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        pytest.fail(f"did not finish in {TIMEOUT} s (zone depth loop?)")
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _zone_then_node(d):
    with d.zone("API", id="api", x=100, y=200, w=600, h=300):
        d.box("API", id="api", x=200, y=300, w=300, h=100)


def _node_then_zone(d):
    d.box("API", id="api", x=200, y=300, w=300, h=100)
    d.zone("API", id="api", x=100, y=200, w=600, h=300)


def _auto_zone_id(d):
    d.box("Z0", x=200, y=300, w=300, h=100)                                   # auto id "z0"
    d.zone("Zone", x=100, y=200, w=600, h=300)                                # auto id "z0" too


COLLISIONS = [  # (id, build, message)
    ("node-after-zone", _zone_then_node, "Z: node id 'api' is already a zone id"),
    ("zone-after-node", _node_then_zone, "Z: zone id 'api' is already a node id"),
    ("auto-zone-id", _auto_zone_id, "Z: zone id 'z0' is already a node id"),
]


@pytest.mark.parametrize("build,message", [c[1:] for c in COLLISIONS], ids=[c[0] for c in COLLISIONS])
def test_zone_and_node_ids_collide(build, message):
    with pytest.raises(ValueError) as err:
        build(Diagram("Z", "Ids"))
    assert str(err.value) == message


def test_yaml_zone_and_node_ids_collide():
    spec = {"id": "Z", "title": "Ids", "zones": [{"id": "api", "label": "API", "x": 100, "y": 200, "w": 600,
                                                  "h": 300, "children": ["api"]}],
            "nodes": [{"id": "api", "title": "API", "x": 200, "y": 300, "w": 300, "h": 100}]}
    with pytest.raises(ValueError) as err:
        from_dict(spec)
    assert str(err.value) == "Z: node id 'api' is already a zone id"


AUTO_IDS = [  # (id, diagram code, node ids expected): titles equal to a zone id get the next free id
    ("zone-fit-children", """
        with d.zone("API", id="api", fit="children"):
            d.box("API", x=200, y=300, w=300, h=100)
     """, ["api-2"]),
    ("snake-row-zones-and-band", """
        d.snake(["Build", "Test", "Ship", "Deploy"], 2, y=200, h=500,
                zones=[{"label": "Build", "id": "build"}, {"label": "Release", "id": "release"}])
        with d.zone("Ops", id="ops", band=(760, 980)):
            d.row(["Monitor", "Ops"])
     """, ["build-2", "test", "ship", "deploy", "monitor", "ops-2"]),
]


@pytest.mark.parametrize("body,ids", [a[1:] for a in AUTO_IDS], ids=[a[0] for a in AUTO_IDS])
def test_auto_node_ids_avoid_zone_ids(body, ids):
    out = _run("from spinagram import Diagram, Theme, build_scene\n"
               "d = Diagram('Z', 'Ids')\n" + textwrap.dedent(body) +
               "build_scene(d, Theme.load('default'))\nprint(' '.join(n.id for n in d.nodes))\n")
    assert out.split() == ids


def test_zone_depth_never_follows_a_zone_to_itself():
    # a zone listing its own id among its children (only reachable by editing the model directly) has depth 0
    out = _run("""
        from spinagram.engine.zones import _depth, _parents
        from spinagram.model import Zone
        zs = [Zone(x=0, y=0, w=10, h=10, id="a", children=["a", "b"]), Zone(x=0, y=0, w=5, h=5, id="b")]
        p = _parents(zs)
        print(sorted(p.items()), _depth("a", p), _depth("b", p))
    """)
    assert out == "[('b', 'a')] 0 1"
