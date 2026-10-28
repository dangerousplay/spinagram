"""The 0.5 release-notes image: a snake through two phase zones, banded zones whose rows the engine places, a
zone anchor and an elbow edge. Rendered into docs/public/assets/release-0-5/ by docs/scripts/render_assets.sh."""
from spinagram import Diagram

d = Diagram("R05", "From commit to production", subtitle="Every card placed by the engine", origin="safe",
            output="release-0-5")

steps = d.snake(["Commit", "Build", "Unit tests", "Image scan", "Stage deploy", "Smoke tests", "Approval",
                 "Production"], cols=4, y=90, h=100, row_gap=50,
                zones=["Build", "Release"])

with d.zone("Observe", id="observe", band=(560, 790), x=0, w=1160, header="right") as observe:
    d.row(["Metrics", "Logs", "Traces"], cols=3)
with d.zone("Respond", id="respond", band=(560, 790), x=1240, w=520):
    pager, runbook = d.row(["Pager", "Runbook"], same_size=True)

d.edge(steps[-1].bottom, observe.at_top(0.25), route="elbow")
d.edge(observe.right, pager)
