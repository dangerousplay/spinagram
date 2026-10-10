"""HTML deck: a self-contained presentation page built from diagrams and a ``deck.yaml``.

Layout: cover (title, subtitle, authors with photo and role) → per section a full-colour
divider slide → one slide per diagram (title band, message, the diagram at full width).
Fonts, logos, photos and diagrams are embedded (base64), so the single ``.html`` file can be
mailed or opened offline. Print = one slide per page.

deck.yaml::

    title: Platform on AWS
    subtitle: Today, target architecture and next steps
    kicker: Architecture review
    date: 2026-10-08
    specs: diagrams/specs            # spec dir(s), relative to deck.yaml
    image: svg                       # svg (vector, default) | png (needs the png extra)
    authors:
      - {name: Jane Doe, role: Platform Engineer, photo: authors/jane.jpeg}
    sections:
      - title: Today
        subtitle: One cluster per account
        slides:
          - {diagram: o05, title: Production in detail, message: "5 + 2 EC2 ..."}
    footer: Source ...

Theme keys (``deck:`` in theme.yaml, all optional)::

    deck:
      accent: primary            # divider gradient light end, slide top rule
      strong: primary-strong     # titles, tags, gradient middle
      deep: primary-deep         # gradient dark end
      page: "#EEF3EF"            # page background behind the slides
      logo: brand/logo-color.png        # slide header + navigation
      logo_negative: brand/logo-white.png  # cover and dividers
"""
from __future__ import annotations

import base64
import html
import mimetypes
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .backends.svg import to_svg
from .layout import build_scene
from .scene import Scene
from .theme import Theme
from .yaml_io import load


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{_b64(path)}"


def _esc(s: Any) -> str:
    return html.escape(str(s or ""))


def _theme_file(theme: Theme, rel: str | None) -> Path | None:
    """Resolve a theme-relative asset (logo, font) across the ``extends`` chain."""
    if not rel:
        return None
    p = Path(rel).expanduser()  # theme loading already made declared assets absolute
    if not p.is_absolute():
        p = theme.root / p
    return p if p.exists() else None


def _font_faces(theme: Theme) -> tuple[str, str, str]:
    """@font-face rules for the heading/body fonts + their CSS family stacks."""
    rules, stacks = [], {}
    for role in ("heading", "body"):
        spec = theme.get("fonts", role) or {}
        fam = spec.get("family", "sans-serif")
        stacks[role] = f"'{fam}', {spec.get('fallback', 'sans-serif')}"
        for key, rel in (spec.get("files") or {}).items():
            path = _theme_file(theme, rel)
            if path is None:
                continue
            weight = "".join(c for c in key if c.isdigit()) or "400"
            style = "italic" if "italic" in key else "normal"
            fmt = {"otf": "opentype", "ttf": "truetype", "woff2": "woff2", "woff": "woff"}.get(path.suffix[1:], "truetype")
            rules.append(f"@font-face{{font-family:'{fam}';font-weight:{weight};font-style:{style};font-display:swap;"
                         f"src:url({_data_uri(path)}) format('{fmt}')}}")
    return "\n".join(rules), stacks["heading"], stacks["body"]


def _diagram_uri(sc: Scene, image: str) -> str:
    if image == "png":
        from .backends.png import PngBackend

        with tempfile.TemporaryDirectory() as tmp:
            (p,) = PngBackend().render([sc], Path(tmp))
            return _data_uri(p)
    return "data:image/svg+xml;base64," + base64.b64encode(to_svg(sc).encode()).decode()


def _fit_height(sc: Scene) -> None:
    """Crop the canvas to the drawn content (+30 px) so tall specs don't carry empty space."""
    from .scene import Connector, Line, Shape, Text

    ys = [0.0]
    for it in sc.items:
        if isinstance(it, Shape) and it.role != "chrome":
            ys.append(it.y + it.h)
        elif isinstance(it, Connector):
            ys += [p[1] for p in it.points]
        elif isinstance(it, Text):
            ys.append(it.y + it.block.font.size * 0.4)
        elif isinstance(it, Line):
            ys += [it.y1, it.y2]
    sc.height = round(max(ys) + 30)


CSS = """
:root{--accent:%(accent)s;--strong:%(strong)s;--deep:%(deep)s;--page:%(page)s;--text:%(text)s;--muted:%(muted)s;
--card:#fff;--line:#dfe6e1}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--page);color:var(--text);font-family:%(body)s}
h1,h2,h3{font-family:%(heading)s;margin:0}
nav{position:sticky;top:0;z-index:2;display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center;padding:10px 16px;
background:var(--card);border-bottom:1px solid var(--line)}
nav img{height:22px;margin-right:8px}nav a{color:var(--strong);text-decoration:none;font-weight:700;font-size:14px}
nav a.sec{color:var(--accent);text-transform:uppercase;letter-spacing:.06em;font-size:12px}
.deck{max-width:1600px;margin:0 auto;padding:24px 16px 48px;display:flex;flex-direction:column;gap:28px}
.slide{scroll-margin-top:84px;border-radius:14px;overflow:hidden;box-shadow:0 2px 14px rgba(0,0,0,.08);background:var(--card)}
.band{aspect-ratio:16/9;color:#fff;position:relative;display:flex;flex-direction:column;justify-content:center;padding:6%% 8%%;
background:radial-gradient(120%% 140%% at 100%% 0%%,var(--accent) 0%%,var(--strong) 45%%,var(--deep) 100%%)}
.band .logo{position:absolute;right:8%%;bottom:8%%;height:clamp(22px,3.2vw,44px)}
.band .kicker{font-weight:700;letter-spacing:.14em;text-transform:uppercase;font-size:clamp(11px,1.3vw,18px);opacity:.85;
margin-bottom:1.2em}
.band h1{font-size:clamp(28px,5vw,72px);line-height:1.05}.band h2{font-size:clamp(30px,6vw,88px);line-height:1}
.band p{font-size:clamp(14px,1.8vw,26px);margin:1em 0 0;max-width:34em;opacity:.92}
.band .num{font-family:%(heading)s;font-weight:700;font-size:clamp(48px,10vw,150px);line-height:1;opacity:.22;position:absolute;
right:7%%;top:8%%}
.authors{position:absolute;left:8%%;bottom:7%%;display:flex;flex-wrap:wrap;gap:12px 28px;align-items:center}
.author{display:flex;align-items:center;gap:12px}
.author img{width:clamp(36px,4.4vw,64px);height:clamp(36px,4.4vw,64px);border-radius:50%%;object-fit:cover;
border:2px solid rgba(255,255,255,.85)}
.author b{display:block;font-size:clamp(13px,1.3vw,19px)}.author span{font-size:clamp(11px,1.05vw,15px);opacity:.85}
.date{font-size:clamp(11px,1.05vw,15px);opacity:.8;margin-top:1.4em}
.head{display:flex;align-items:flex-start;gap:16px;padding:22px 28px 16px;border-top:8px solid var(--accent)}
.head .tag{flex:none;font-weight:700;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#fff;
background:var(--strong);border-radius:999px;padding:4px 10px;margin-top:4px}
.head h3{color:var(--strong);font-size:clamp(20px,2.2vw,30px)}
.head p{margin:6px 0 0;color:var(--muted);font-size:clamp(14px,1.2vw,17px);max-width:70em}
.head .brand{margin-left:auto;height:24px;flex:none;margin-top:6px}
.body{padding:0 28px 26px}.body img{display:block;width:100%%;height:auto}
footer{max-width:1600px;margin:0 auto;padding:0 16px 32px;color:var(--muted);font-size:13px}
@media (max-width:640px){.head{flex-wrap:wrap;padding:18px 16px 12px}.head .brand{display:none}.body{padding:0 12px 16px}
.authors{position:static;margin-top:1.5em}.band{aspect-ratio:auto;min-height:56vw}}
@media print{body{background:#fff}nav{display:none}.deck{padding:0;gap:0}
.slide{box-shadow:none;border-radius:0;break-after:page}.band{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""


def build_deck(deck_file: str | Path, theme: Theme | str | Path | None = None, out: str | Path | None = None) -> Path:
    """Render ``deck.yaml`` into one self-contained HTML file; returns its path."""
    deck_file = Path(deck_file).resolve()
    base = deck_file.parent
    cfg = yaml.safe_load(deck_file.read_text(encoding="utf-8")) or {}
    th = theme if isinstance(theme, Theme) else Theme.load(theme or cfg.get("theme"))
    specs = cfg.get("specs") or ["."]
    specs = specs if isinstance(specs, list) else [specs]
    diagrams = {d.id: d for s in specs for d in load(base / s)}
    image = cfg.get("image", "svg")

    dk = th.get("deck") or {}
    col = lambda k, dflt: th.color(dk.get(k, dflt))  # noqa: E731
    faces, heading, body = _font_faces(th)
    css = CSS % {"accent": col("accent", "primary"), "strong": col("strong", "primary-strong"),
                 "deep": col("deep", "primary-deep"), "page": th.color(dk.get("page", "#F4F5F4")),
                 "text": col("text", "text"), "muted": col("muted", "text-muted"), "heading": heading, "body": body}
    logo = _theme_file(th, dk.get("logo") or (th.get("chrome", "footer") or {}).get("logo"))
    logo_neg = _theme_file(th, dk.get("logo_negative"))
    logo_tag = lambda p, cls, alt="": f'<img class="{cls}" src="{_data_uri(p)}" alt="{alt}">' if p else ""  # noqa: E731

    authors = []
    for a in cfg.get("authors") or []:
        photo = base / a["photo"] if a.get("photo") else None
        img = f'<img src="{_data_uri(photo)}" alt="">' if photo and photo.exists() else ""
        authors.append(f'<div class="author">{img}<div><b>{_esc(a.get("name"))}</b>'
                       f'<span>{_esc(a.get("role"))}</span></div></div>')

    nav = [logo_tag(logo, "", "logo")]
    slides = [f'''<section class="slide band" id="capa">
  <div class="kicker">{_esc(cfg.get("kicker"))}</div>
  <h1>{_esc(cfg.get("title"))}</h1>
  <p>{_esc(cfg.get("subtitle"))}</p>
  {f'<div class="date">{_esc(cfg["date"])}</div>' if cfg.get("date") else ""}
  <div class="authors">{"".join(authors)}</div>
  {logo_tag(logo_neg, "logo", "logo")}
</section>''']
    for si, sec in enumerate(cfg.get("sections") or [], 1):
        sid = f"s{si}"
        nav.append(f'<a class="sec" href="#{sid}">{si:02d} · {_esc(sec["title"])}</a>')
        slides.append(f'''<section class="slide band" id="{sid}">
  <div class="num">{si:02d}</div><div class="kicker">{_esc(sec.get("kicker", f"Seção {si:02d}"))}</div>
  <h2>{_esc(sec["title"])}</h2><p>{_esc(sec.get("subtitle"))}</p>
  {logo_tag(logo_neg, "logo", "logo")}
</section>''')
        for sl in sec.get("slides") or []:
            d = diagrams.get(sl["diagram"])
            if d is None:
                raise KeyError(f"deck slide references unknown diagram {sl['diagram']!r}; known: {sorted(diagrams)}")
            sc = build_scene(d, th)
            _fit_height(sc)
            title = sl.get("title") or d.title
            nav.append(f'<a href="#{d.id}">{_esc(title)}</a>')
            slides.append(f'''<section class="slide" id="{d.id}">
  <div class="head"><span class="tag">{_esc(sec["title"])}</span>
    <div><h3>{_esc(title)}</h3><p>{_esc(sl.get("message") or d.subtitle or "")}</p></div>
    {logo_tag(logo, "brand")}</div>
  <div class="body"><img src="{_diagram_uri(sc, image)}" alt="{_esc(title)}"></div>
</section>''')

    page = f"""<!doctype html>
<html lang="{_esc(cfg.get('lang', 'pt-BR'))}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(cfg.get("title"))}</title>
<style>{faces}
{css}</style></head>
<body>
<nav>{"".join(nav)}</nav>
<main class="deck">
{chr(10).join(slides)}
</main>
<footer>{_esc(cfg.get("footer"))}</footer>
</body></html>
"""
    dst = Path(out) if out else base / f"{deck_file.stem}.html"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(page, encoding="utf-8")
    return dst
