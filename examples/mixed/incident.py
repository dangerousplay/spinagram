"""Architecture and process on one slide: the monitoring stack that raises an alert, and the swimlane
activity the on-call team follows when it fires."""
from spinagram import Diagram

d = Diagram("M02", "When an alert fires", subtitle="An architecture region and an activity with swimlanes",
            layout={"engine": "flex", "direction": "down", "gap": 28})
d.stylesheet("mixed.css")

with d.group("Monitoring", id="stack", class_="arch", direction="right", gap=120, padding=18):
    app = d.box("Shop", text="Kubernetes", icon="k8s:pod")
    prom = d.box("Prometheus", text="alert rules", icon="selfhosted:prometheus")
    pager = d.box("PagerDuty", text="on-call rota", icon="selfhosted:pagerduty", class_="hero")
app.to(prom, "metrics") >> pager

with d.activity("Incident response", id="response", class_="flow", direction="right") as act:
    with act.sequence():
        with act.lane("On-call"):
            act.start()
            ack = act.action("Acknowledge")
            act.action("Triage")
        with act.lane("Team"):
            with act.parallel() as par:
                with par.branch():
                    act.action("Mitigate")
                with par.branch():
                    act.action("Update status page")
        with act.lane("On-call"):
            act.action("Write postmortem")
            act.end()

pager.to(ack, "pages", class_="link")

diagram = d
