"""CSS gallery for the docs: one small diagram per styling feature (stylesheets next to this file).

Render: `uv run python docs/scripts/css_gallery.py` (writes cropped SVGs to docs/public/assets/css/).
"""
from spinagram import Diagram, StateMachine


def _d(id: str, title: str, sheet: str, direction: str = "right") -> Diagram:
    d = Diagram(id, title, layout={"engine": "layered", "direction": direction})
    d.stylesheet(sheet)
    return d


def boxes() -> Diagram:
    d = _d("G01", "Fills, strokes and corners", "01-boxes.css")
    d.box("Soft", text="theme tokens", class_="soft") >> d.box("Round", text="border-radius: 40px", class_="round") \
        >> d.box("Sharp", text="stroke-width: 6", class_="sharp")
    return d


def dashes() -> Diagram:
    d = _d("G02", "Dashes and transparency", "02-dashes.css")
    d.box("Dashed", text="12 6", class_="dashed") >> d.box("Dotted", text="2 5", class_="dotted")
    d.box("Faded", text="opacity: 0.45", class_="faded") >> d.box("Glass", text="fill-opacity: 0.15", class_="glass")
    return d


def shadows() -> Diagram:
    d = _d("G03", "Shadows", "03-shadows.css")
    d.box("Lift", text="soft drop shadow", class_="lift") >> d.box("Glow", text="no offset", class_="glow") \
        >> d.box("Hard", text="no blur", class_="hard")
    return d


def edges() -> Diagram:
    d = _d("G04", "Edges and markers", "04-edges.css")
    for cls, label in (("open", "open-arrow"), ("diamond", "open-diamond → diamond"), ("circle", "circle, dashed"),
                       ("bar", "bar"), ("both", "both ends, 50 %")):
        d.box("From", id=f"{cls}-a").to(d.box("To", id=f"{cls}-b"), label, class_=cls)
    return d


def text() -> Diagram:
    d = _d("G05", "Text", "05-text.css")
    with d.group("Group label"):
        a = d.box("Bold title", text="::title")
        b = d.box("Quiet title", text="italic, muted", class_="quiet")
    c = d.box("Body", text="purple italic body", class_="note")
    a.to(b, "edge label")
    b >> c
    return d


def tokens() -> Diagram:
    d = _d("G06", "Custom properties and tokens", "06-tokens.css")
    d.box("Brand", text="var(--brand)") >> d.box("Risky", text="var(--alert)", class_="risky") \
        >> d.box("Muted", text="neutral-soft", class_="muted")
    return d


def selectors() -> Diagram:
    d = _d("G07", "Selectors and inheritance", "07-selectors.css")
    with d.group("Team", class_="team"):
        api = d.box("API", text="first child", class_="done")
        worker = d.box("Worker", text="not .done")
    db = d.add("data", "Orders DB", id="db", class_="done")
    api >> worker >> db
    return d


def behavior() -> StateMachine:
    sm = StateMachine("G08", "Behavior kinds")
    sm.stylesheet("08-behavior.css")
    start = sm.initial  # first node: the layout starts the flow here
    idle, busy = sm.state("Idle"), sm.state("Busy", do="work")
    ok = sm.choice()
    start >> idle
    idle.on("start", busy)
    busy >> ok
    ok.on("[done]", sm.final)
    ok.on("[retry]", idle)
    return sm


diagrams = [boxes(), dashes(), shadows(), edges(), text(), tokens(), selectors(), behavior()]
