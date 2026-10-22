"""Per-character glyph fallback (roadmap T2): role font → body font → bundled symbol fonts."""
from __future__ import annotations

from ..scene import Connector, Run, Scene, Shape, TableGrid, Text
from ..text import bundled_fonts, covers
from ..theme import FontRef, Theme


def chain(font: FontRef, theme: Theme) -> list[FontRef]:
    """Fonts tried, in order, for a character ``font`` lacks."""
    body = theme.font("body", font.weight, font.size, font.italic)
    first = [body] if (body.family, body.file) != (font.family, font.file) else []
    return first + bundled_fonts(font.size, font.weight)


def runs(line: str, font: FontRef, fallbacks: list[FontRef]) -> list[Run]:
    """``line`` cut into runs of one font each: the primary where it has the glyph, else the first fallback
    that has it (the primary when none does)."""
    out: list[Run] = []
    for ch in line:
        f = font if ch.isspace() or covers(font, ch) else next((fb for fb in fallbacks if covers(fb, ch)), font)
        if out and out[-1].font is f:
            out[-1].text += ch
        else:
            out.append(Run(ch, f))
    return out


def _blocks(scene: Scene):
    for it in scene.items:
        if isinstance(it, Shape) and it.label:
            yield from it.label.blocks
        elif isinstance(it, Text):
            yield it.block
        elif isinstance(it, Connector) and it.label is not None and it.label.label:
            yield from it.label.label.blocks
        elif isinstance(it, TableGrid):
            for row in it.cells:
                for c in row:
                    yield c.block


def role(font: FontRef, theme: Theme) -> str:
    """The theme font role a font came from (heading or body; bold text reads as heading when they match)."""
    fams = {r: (theme.get("fonts", r) or {}).get("family") for r in ("heading", "body")}
    if fams["heading"] == fams["body"]:
        return "heading" if font.weight >= 600 else "body"
    return "heading" if font.family == fams["heading"] else "body"


def apply(scene: Scene, theme: Theme) -> None:
    """Give every text block that needs a fallback its runs, and record each (char, role, fallback) once."""
    seen: dict[tuple[str, str], str] = {}
    for b in _blocks(scene):
        if all(ch.isspace() or covers(b.font, ch) for ln in b.lines for ch in ln):
            continue
        fbs = chain(b.font, theme)
        b.runs = [runs(ln, b.font, fbs) for ln in b.lines]
        r = role(b.font, theme)
        for line in b.runs:
            for run in line:
                if run.font is not b.font:
                    for ch in run.text:
                        seen.setdefault((ch, r), run.font.family)
    scene.fallbacks = [(ch, r, fam) for (ch, r), fam in seen.items()]
