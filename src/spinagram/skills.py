"""Agent skills shipped with spinagram: list them, print them and install them for any coding agent.

A skill is a folder with a ``SKILL.md`` (YAML front matter with ``name`` and ``description``, then
Markdown instructions) plus optional ``references/`` and ``examples/``. That layout is the common
"agent skills" format, so the same folder works in every tool that reads it; only the folder the
tool looks in differs. ``AGENTS`` maps the usual tools to their project and user folders; any other
tool takes ``dest``.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).parent / "agent_skills"

# agent: (folder in a project, folder for the user); paths as each tool documents them
AGENTS: dict[str, tuple[str, str]] = {
    "agents": (".agents/skills", "~/.agents/skills"),  # tool-neutral location, read by several agents
    "claude": (".claude/skills", "~/.claude/skills"),
    "codex": (".agents/skills", "~/.agents/skills"),
    "copilot": (".github/skills", "~/.copilot/skills"),
    "cursor": (".cursor/skills", "~/.cursor/skills"),
    "gemini": (".gemini/skills", "~/.gemini/skills"),
    "opencode": (".opencode/skills", "~/.config/opencode/skills"),
}


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path

    @property
    def summary(self) -> str:
        """The description's first sentence."""
        first, dot, _ = self.description.partition(". ")
        return first + ("." if dot else "")


def _front_matter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    return yaml.safe_load(text[3:end]) or {} if end > 0 else {}


def available() -> dict[str, Skill]:
    """The bundled skills by name."""
    out = {}
    for md in sorted(ROOT.glob("*/SKILL.md")):
        meta = _front_matter(md.read_text(encoding="utf-8"))
        name = meta.get("name") or md.parent.name
        out[name] = Skill(name, " ".join(str(meta.get("description", "")).split()), md.parent)
    return out


def get(name: str) -> Skill:
    skills = available()
    if name not in skills:
        raise KeyError(f"unknown skill {name!r}; available: {', '.join(skills)}")
    return skills[name]


def target(agent: str, user: bool = False, base: Path | None = None) -> Path:
    """The skills folder ``agent`` reads: in the project at ``base`` (default: cwd), or for the user."""
    if agent not in AGENTS:
        raise ValueError(f"unknown agent {agent!r}; known: {', '.join(AGENTS)} (or pass a folder with --dest)")
    project, home = AGENTS[agent]
    return Path(home).expanduser() if user else (base or Path.cwd()) / project


def install(names: list[str] | None, dest: Path, *, link: bool = False, force: bool = False) -> list[Path]:
    """Copy (or symlink, with ``link``) each skill into ``dest/<name>``; all of them when ``names`` is empty.

    An existing ``dest/<name>`` is replaced only with ``force``.
    """
    skills = [get(n) for n in names] if names else list(available().values())
    dest.mkdir(parents=True, exist_ok=True)
    clashes = [dest / s.name for s in skills if (dest / s.name).exists() or (dest / s.name).is_symlink()]
    if clashes and not force:
        raise FileExistsError(f"already installed: {', '.join(map(str, clashes))} (use --force to replace)")
    done = []
    for s in skills:
        out = dest / s.name
        if out.is_symlink() or out.is_file():
            out.unlink()
        elif out.exists():
            shutil.rmtree(out)
        if link:
            os.symlink(s.path.resolve(), out, target_is_directory=True)
        else:
            shutil.copytree(s.path, out, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        done.append(out)
    return done
