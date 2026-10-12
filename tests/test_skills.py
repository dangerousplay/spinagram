"""Bundled agent skills: discovery, installation for any agent and the CSS skill's examples."""
from __future__ import annotations

from pathlib import Path

import pytest

from spinagram import cli, css, skills

REPO = Path(__file__).resolve().parents[1]
CSS_SKILL = skills.ROOT / "spinagram-css"


def test_bundled_skills_have_front_matter():
    found = skills.available()
    assert {"spinagram", "spinagram-css"} <= set(found)
    for s in found.values():
        assert s.path.name == s.name  # agents match the folder name against `name`
        assert s.description and len(s.description) <= 1024
        assert s.summary.endswith(".")


def test_install_copies_and_refuses_to_overwrite(tmp_path):
    out = skills.install(["spinagram-css"], tmp_path)
    assert out == [tmp_path / "spinagram-css"]
    assert (tmp_path / "spinagram-css" / "references" / "recipes.css").is_file()
    assert not (tmp_path / "spinagram-css").is_symlink()
    with pytest.raises(FileExistsError):
        skills.install(["spinagram-css"], tmp_path)
    (tmp_path / "spinagram-css" / "stale.txt").write_text("old")
    skills.install(["spinagram-css"], tmp_path, force=True)
    assert not (tmp_path / "spinagram-css" / "stale.txt").exists()


def test_install_links_and_installs_all_by_default(tmp_path):
    skills.install(None, tmp_path, link=True)
    for name in skills.available():
        assert (tmp_path / name).is_symlink()
        assert (tmp_path / name / "SKILL.md").is_file()
    skills.install(None, tmp_path, force=True)  # a copy replaces a link
    assert not (tmp_path / "spinagram").is_symlink()


def test_agent_targets(tmp_path):
    assert skills.target("claude", base=tmp_path) == tmp_path / ".claude/skills"
    assert skills.target("codex", base=tmp_path) == skills.target("agents", base=tmp_path)
    assert skills.target("claude", user=True) == Path("~/.claude/skills").expanduser()
    with pytest.raises(ValueError, match="--dest"):
        skills.target("nope")


def test_cli_install_dedupes_shared_folders(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["skills", "install", "spinagram", "-a", "codex", "-a", "agents", "-a", "claude"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2  # codex and agents share .agents/skills
    assert (tmp_path / ".agents/skills/spinagram/SKILL.md").is_file()
    assert (tmp_path / ".claude/skills/spinagram/SKILL.md").is_file()
    assert cli.main(["skills", "install", "spinagram", "-a", "claude"]) == 1
    assert cli.main(["skills", "install", "--dest", "x", "-a", "claude"]) == 2
    assert cli.main(["skills", "install", "--dest", str(tmp_path / "any"), "spinagram"]) == 0


def test_cli_list_show_path(capsys):
    assert cli.main(["skills", "list"]) == 0
    assert "spinagram-css" in capsys.readouterr().out
    assert cli.main(["skills", "show", "spinagram-css"]) == 0
    assert capsys.readouterr().out.startswith("---\nname: spinagram-css")
    assert cli.main(["skills", "path", "spinagram-css"]) == 0
    assert capsys.readouterr().out.strip() == str(CSS_SKILL)
    assert cli.main(["skills", "show", "nope"]) == 2


def test_recipes_parse_cleanly():
    _, errors = css.parse((CSS_SKILL / "references" / "recipes.css").read_text(), "recipes.css")
    assert not errors


def test_css_examples_match_the_repository_showcase():
    bundled = {p.name: p.read_text() for p in (CSS_SKILL / "examples").iterdir() if p.is_file()}
    showcase = {p.name: p.read_text() for p in (REPO / "examples" / "showcase").iterdir() if p.is_file()}
    assert bundled == showcase


def test_css_examples_pass_check(capsys):
    assert cli.main(["check", str(CSS_SKILL / "examples")]) == 0
    assert "0 issue(s)" in capsys.readouterr().out
