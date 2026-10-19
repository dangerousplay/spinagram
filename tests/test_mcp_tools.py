"""MCP tool functions (spec: .specs/features/mcp-server/spec.md, MCP-02, 05..11 and edge cases)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from spinagram.cli import main
from spinagram.mcp_server.tools import Tools

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
OVERFLOW = """\
id: OV
title: Overflow
nodes:
  - {id: a, title: "A box whose title is far too long to fit in forty pixels", x: 100, y: 200, w: 40, h: 30}
"""


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "root"
    (r / "specs").mkdir(parents=True)
    shutil.copy(EXAMPLES / "decision.yaml", r / "specs" / "decision.yaml")
    shutil.copy(EXAMPLES / "quickstart.yaml", r / "specs" / "quickstart.yaml")
    (r / "specs" / "overflow.yaml").write_text(OVERFLOW, encoding="utf-8")
    return r


def cli(capsys, *argv) -> str:
    capsys.readouterr()
    main(list(argv))
    return capsys.readouterr().out


def test_render_writes_what_the_cli_writes(root, tmp_path, capsys):  # MCP-02
    t = Tools(root)
    res = t.render(["specs/decision.yaml"], formats=["svg"])
    cli_out = tmp_path / "cli"
    cli(capsys, "render", str(root / "specs" / "decision.yaml"), "-f", "svg", "-o", str(cli_out))
    assert sorted(Path(p).name for p in res["written"]) == sorted(p.name for p in cli_out.iterdir())
    assert all(not Path(p).is_absolute() and (root / p).is_file() for p in res["written"])
    assert all(Path(p).parts[0] == "out" for p in res["written"])            # default out: <root>/out
    svg = next(p for p in res["written"] if p.endswith(".svg"))
    assert (root / svg).read_bytes() == (cli_out / Path(svg).name).read_bytes()


def test_render_only_and_relative_out(root):  # MCP-02 (only, out), edge case: relative out under root
    res = Tools(root).render(["specs"], formats=["svg"], only=["EX2"], out="build/diagrams")
    assert [p for p in res["written"] if p.endswith(".svg")] == ["build/diagrams/EX2-when-does-a-change-need-review.svg"]
    assert (root / "build/diagrams/EX2-when-does-a-change-need-review.svg").is_file()


def test_check_matches_the_cli(root, capsys):  # MCP-05
    res = Tools(root).check(["specs"])
    lines = cli(capsys, "check", str(root / "specs")).splitlines()
    assert res["diagrams"] == 3
    assert res["issues"] and res["issues"] == lines[:-1]                     # last CLI line is the summary
    assert lines[-1] == f"3 diagram(s), {len(res['issues'])} issue(s)"


def test_layout_matches_the_cli(root, capsys):  # MCP-06
    assert Tools(root).layout_yaml(["specs/quickstart.yaml"]) == cli(capsys, "layout", str(root / "specs/quickstart.yaml"))


def test_styles_matches_check_json(root, capsys):  # MCP-07
    t = Tools(root)
    assert t.styles(["specs/decision.yaml"]) == json.loads(cli(capsys, "check", str(root / "specs/decision.yaml"),
                                                               "--json"))
    both = t.styles(["specs/decision.yaml", "specs/quickstart.yaml"])
    assert isinstance(both, list) and len(both) == 2
    sel = t.styles(["specs/decision.yaml"], select="node")
    assert sel == json.loads(cli(capsys, "check", str(root / "specs/decision.yaml"), "--json", "--select", "node"))


def test_icons_search_matches_the_cli(root, tmp_path, monkeypatch, capsys):  # MCP-08
    from spinagram import icons

    monkeypatch.setenv("SPINAGRAM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    pack = tmp_path / "pack"
    pack.mkdir()
    for n in ("dot", "dot-big", "square"):
        (pack / f"{n}.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    icons.register("tiny", {"type": "dir", "path": str(pack)})
    icons.fetch(icons.registry()["tiny"])
    t = Tools(root)
    assert t.icons_search("dot", pack=["tiny"]) == cli(capsys, "icons", "search", "dot", "--pack", "tiny").split()
    assert t.icons_search("dot", pack=["tiny"]) == ["tiny:dot", "tiny:dot-big"]
    assert t.icons_search("dot", pack=["tiny"], limit=1) == ["tiny:dot"]
    assert t.icons_search("nothing-like-this", pack=["tiny"]) == []


@pytest.mark.parametrize("call", [
    lambda t: t.render(["../outside.yaml"]),
    lambda t: t.check(["/etc"]),
    lambda t: t.render(["specs"], out="/tmp/elsewhere"),
    lambda t: t.layout_yaml(["specs/../../outside.yaml"]),
])
def test_paths_outside_root_are_refused(root, call):  # MCP-09
    with pytest.raises(ValueError, match="^path outside root: "):
        call(Tools(root))
    assert not (root / "out").exists()


def test_symlink_out_of_root_is_refused(root, tmp_path):  # edge case: symlink pointing outside
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "x.yaml").write_text(OVERFLOW, encoding="utf-8")
    (root / "link").symlink_to(tmp_path / "secret")
    with pytest.raises(ValueError, match="^path outside root: link/x.yaml$"):
        Tools(root).check(["link/x.yaml"])


def test_cli_error_messages(root):  # MCP-10: the message the CLI prints after "spinagram: error: "
    t = Tools(root)
    with pytest.raises(ValueError, match="^no diagrams found$"):
        t.check([])
    with pytest.raises(ValueError, match="^no diagrams found$"):
        t.check(["specs"], only=["NOPE"])
    with pytest.raises(FileNotFoundError):
        t.check(["specs/missing.yaml"])


def test_server_defaults_and_call_overrides(root, monkeypatch):  # MCP-11
    seen = {}

    def fake_render(diagrams, out, *, theme, formats, gallery, layout):
        seen.update(theme=theme, formats=formats, layout=layout)
        return []

    monkeypatch.setattr("spinagram.mcp_server.tools.api.render", fake_render)
    t = Tools(root, theme="default", layout="flex", formats=["svg"])
    t.render(["specs/decision.yaml"])
    assert (seen["theme"].root.name, seen["formats"], seen["layout"]) == ("default", ["svg"], "flex")
    t.render(["specs/decision.yaml"], formats=["pptx"], layout="dot")
    assert (seen["formats"], seen["layout"]) == (["pptx"], "dot")
    assert Tools(root).formats == ["svg", "png"]                              # CLI default -f svg,png


# T9 (validation.md, iteration 1) ---------------------------------------------------------------------
def _theme_dir(where: Path) -> Path:
    where.mkdir(parents=True)
    (where / "theme.yaml").write_text("extends: default\ncolors: {brand: '#123456'}\n", encoding="utf-8")
    return where


def test_server_theme_outside_root(root, tmp_path, monkeypatch):  # MCP-11: -t is not root-checked
    theme = _theme_dir(tmp_path / "themes" / "brand")
    assert Tools(root, theme=str(theme)).check(["specs/decision.yaml"])["diagrams"] == 1
    monkeypatch.chdir(tmp_path)                                               # relative to the server's cwd at start
    t = Tools(root, theme="themes/brand")
    monkeypatch.chdir(root)
    assert t.theme == str(theme.resolve())
    assert t.check(["specs/decision.yaml"])["diagrams"] == 1


def test_call_theme_path_stays_confined(root, tmp_path):  # MCP-09 applies to tool arguments
    _theme_dir(tmp_path / "outside")
    with pytest.raises(ValueError, match="^path outside root: ../outside$"):
        Tools(root).render(["specs/decision.yaml"], formats=["svg"], theme="../outside")


def test_install_makes_an_existing_theme_absolute(tmp_path, monkeypatch):  # INST-04
    from spinagram.mcp_server.install import server_args

    _theme_dir(tmp_path / "brand")
    monkeypatch.chdir(tmp_path)
    assert server_args(theme="brand") == ["-t", str((tmp_path / "brand").resolve())]
    assert server_args(theme="default") == ["-t", "default"]                 # a built-in name stays
