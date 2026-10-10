"""Python DSL example: render with `spinagram render examples/ -f svg,pptx`."""
from spinagram import Diagram

d = Diagram("EX1", "Release flow", subtitle="Evidence decides the path, not the requester",
            source="Example diagram · spinagram")

build, test, gate = d.row(
    [{"title": "Build", "text": "Pipeline produces a signed artifact"},
     {"title": "Stress & chaos", "text": "Restart, rollout and cold start within SLO"},
     {"title": "Risk gate", "style": "dark", "text": "Scores evidence, history and open debt"}],
    x=80, y=220, w=440, h=220, gap=100)
d.chain(build, test, gate)

ok = d.box("Deploy", text="Standard change, no extra step", x=1340, y=560, w=500, h=150)
hold = d.box("Low-impact window", text="Or manager approval", style="warning", x=700, y=560, w=500, h=150)
d.edge(gate.bottom, ok.top, label="green")
d.edge(gate, hold, label="red", color="warning")

d.table(["Signal", "Source", "Effect"],
        [["Chaos test failed", "Stress cluster", "Window or approval"],
         ["Open resilience debt", "Issue tracker", "Adds to the score"]],
        x=80, y=760, widths=[400, 400, 600], row_height=70)

diagram = d
