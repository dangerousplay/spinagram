"""Theme glyph map: characters the brand font lacks replaced before layout (GLM-01..04)."""
from __future__ import annotations

import string

import pytest
import yaml

from spinagram import Diagram, Theme, build_scene
from spinagram.backends.svg import to_svg
from spinagram.engine import model_passes
from spinagram.qa import check


def _theme(tmp_path, glyph_map, fonts=None, name="t"):
    root = tmp_path / name
    root.mkdir()
    data = {"text": {"glyph_map": glyph_map}} | ({"fonts": fonts} if fonts else {})
    (root / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    return Theme.load(root)


def _base():
    d = Diagram("G", "Plain")
    d.box("A", id="a", x=200, y=200, w=400, h=160)
    d.box("B", id="b", x=900, y=200, w=400, h=160)
    return d


def _with(fn):
    def make():
        d = _base()
        fn(d)
        return d
    return make


LOCATIONS = [  # (id, put "x → y" there, read it back from the passed model)
    ("title", _with(lambda d: setattr(d, "title", "x → y")), lambda d: d.title),
    ("subtitle", _with(lambda d: setattr(d, "subtitle", "x → y")), lambda d: d.subtitle),
    ("kicker", _with(lambda d: setattr(d, "kicker", "x → y")), lambda d: d.kicker),
    ("source", _with(lambda d: setattr(d, "source", "x → y")), lambda d: d.source),
    ("node-title", _with(lambda d: setattr(d.nodes[0], "title", "x → y")), lambda d: d.nodes[0].title),
    ("node-title-list", _with(lambda d: setattr(d.nodes[0], "title", ["x → y", "z"])),
     lambda d: d.nodes[0].title[0]),
    ("node-text", _with(lambda d: setattr(d.nodes[0], "text", "x → y")), lambda d: d.nodes[0].text),
    ("node-lines", _with(lambda d: setattr(d.nodes[0], "lines", ["z", "x → y"])), lambda d: d.nodes[0].lines[1]),
    ("edge-label", _with(lambda d: d.edge("a", "b", "x → y")), lambda d: d.edges[0].label),
    ("zone-label", _with(lambda d: d.zone("x → y", x=150, y=150, w=1200, h=300)), lambda d: d.zones[0].label),
    ("table-header", _with(lambda d: d.table(["x → y", "b"], [["1", "2"]], x=200, y=500, widths=[200, 200])),
     lambda d: d.tables[0].header[0]),
    ("table-row", _with(lambda d: d.table(["a", "b"], [["1", "x → y"]], x=200, y=500, widths=[200, 200])),
     lambda d: d.tables[0].rows[0][1]),
    ("fixed-legend", _with(lambda d: d.set_legend([("primary", "x → y")], x=200, y=900)),
     lambda d: d.legend.items[0][1]),
    ("legend-card", _with(lambda d: d.add_legend({"style:soft": "x → y"}, title="x → y")),
     lambda d: d.annotations.legend.items["style:soft"]),
    ("legend-card-title", _with(lambda d: d.add_legend({"style:soft": "s"}, title="x → y")),
     lambda d: d.annotations.legend.title),
    ("step", _with(lambda d: d.step("x → y", on="a")), lambda d: d.annotations.steps[0].text),
    ("callout-text", _with(lambda d: d.callout("a", "x → y")), lambda d: d.annotations.callouts[0].text),
    ("callout-title", _with(lambda d: d.callout("a", "t", title="x → y")), lambda d: d.annotations.callouts[0].title),
    ("snake-step", lambda: _snake(), lambda d: d.nodes[0].title),
]


def _snake():
    d = Diagram("G", "Plain")
    d.snake(["x → y", "b"], 2, y=200, h=120)
    return d


@pytest.mark.parametrize("make,read", [loc[1:] for loc in LOCATIONS], ids=[loc[0] for loc in LOCATIONS])
def test_every_text_location_is_mapped(tmp_path, make, read):
    theme = _theme(tmp_path, {"→": "›"})
    d = make()
    assert read(model_passes.apply(d, theme)) == "x › y"                       # replaced before layout
    assert read(d) == "x → y"                                                  # the spec is not mutated
    sc = build_scene(d, theme)
    assert "→" not in to_svg(sc)                                               # nothing draws the mapped char
    assert [(i.item, i.kind, i.detail, i.severity) for i in check(sc) if i.kind == "glyph-mapped"] == [
        ("glyphs", "glyph-mapped", "'→' (U+2192) replaced by '›' (theme glyph_map)", "P2")]


MAPS = [  # (id, glyph map, node title, expected title, expected glyph-mapped details)
    ("one", {"→": "›"}, "a → b → c", "a › b › c", ["'→' (U+2192) replaced by '›' (theme glyph_map)"]),
    ("two-chars", {"→": "›", "×": "x"}, "2 × 3 → 6", "2 x 3 › 6",
     ["'→' (U+2192) replaced by '›' (theme glyph_map)", "'×' (U+00D7) replaced by 'x' (theme glyph_map)"]),
    ("only-seen-chars", {"→": "›", "×": "x"}, "a → b", "a › b", ["'→' (U+2192) replaced by '›' (theme glyph_map)"]),
    ("multi-char", {"→": "->"}, "a → b", "a -> b", ["'→' (U+2192) replaced by '->' (theme glyph_map)"]),
    ("empty", {"™": ""}, "Brand™", "Brand", ["'™' (U+2122) replaced by '' (theme glyph_map)"]),
    ("identity", {"→": "→"}, "a → b", "a → b", []),
    ("not-present", {"→": "›"}, "a to b", "a to b", []),
    ("no-chain", {"a": "b", "b": "c"}, "ab", "bc", ["'a' (U+0061) replaced by 'b' (theme glyph_map)",
                                                     "'b' (U+0062) replaced by 'c' (theme glyph_map)"]),
]


@pytest.mark.parametrize("gm,title,want,details", [m[1:] for m in MAPS], ids=[m[0] for m in MAPS])
def test_maps(tmp_path, gm, title, want, details):
    theme = _theme(tmp_path, gm)
    d = Diagram("G", "Plain")
    d.box(title, id="a", x=200, y=200, w=600, h=160)
    assert model_passes.apply(d, theme).nodes[0].title == want
    sc = build_scene(d, theme)
    assert sc.shapes()["a"].label.blocks[0].lines == [want]
    assert [i.detail for i in check(sc) if i.kind == "glyph-mapped"] == details


def test_unchanged_diagram_is_not_copied(tmp_path):
    d = _base()
    assert model_passes.apply(d, _theme(tmp_path, {"→": "›"})) is d          # nothing to map, nothing to place


def test_engine_laid_out_diagram_is_mapped(tmp_path):
    d = Diagram("G", "Auto")
    d.box("x → y", id="a")
    sc = build_scene(d, _theme(tmp_path, {"→": "›"}))
    assert sc.laid_out and sc.shapes()["a"].label.blocks[0].lines == ["x › y"]


def test_mapped_char_is_not_reported_missing(tmp_path):
    from test_engine_glyphs import make_font

    ascii_ = string.printable.strip() + " "
    font = make_font(tmp_path / "brand.ttf", ascii_ + "›", "Brand")
    fonts = {r: {"family": "Brand", "files": {"400": str(font), "700": str(font)}} for r in ("heading", "body")}
    d = Diagram("G", "Plain")
    d.box("a → b", id="a", x=200, y=200, w=600, h=160)
    unmapped = check(build_scene(d, _theme(tmp_path, {}, fonts, "plain")))
    assert [i.detail for i in unmapped if i.kind == "glyph-missing"] != []      # the brand font lacks '→'
    mapped = check(build_scene(d, _theme(tmp_path, {"→": "›"}, fonts, "mapped")))
    assert [i.kind for i in mapped if i.kind in ("glyph-missing", "glyph-mapped")] == ["glyph-mapped"]


BAD = [  # (id, glyph map YAML, error)
    ("two-char-key", {"->": "›"}, "theme 't': text.glyph_map key '->' is not a single character"),
    ("empty-key", {"": "›"}, "theme 't': text.glyph_map key '' is not a single character"),
    ("number-key", {1: "›"}, "theme 't': text.glyph_map key 1 is not a single character"),
    ("non-string-value", {"→": 3}, "theme 't': text.glyph_map value for '→' must be a string, got 3"),
    ("not-a-mapping", ["→"], "theme 't': text.glyph_map must be a mapping of characters, got ['→']"),
]


@pytest.mark.parametrize("gm,msg", [b[1:] for b in BAD], ids=[b[0] for b in BAD])
def test_invalid_map(tmp_path, gm, msg):
    with pytest.raises(ValueError) as err:
        _theme(tmp_path, gm)
    assert str(err.value) == msg


def test_map_merges_through_extends(tmp_path):
    base = _theme(tmp_path, {"→": "›"}, name="base")
    child = tmp_path / "child"
    child.mkdir()
    (child / "theme.yaml").write_text(f"extends: {base.root}\ntext:\n  glyph_map: {{'×': x}}\n")
    assert Theme.load(child).get("text", "glyph_map") == {"→": "›", "×": "x"}
