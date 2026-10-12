"""CSS-like styling: `spinagram render examples/styling/styled.py -f svg,pptx -o out/`."""
from spinagram import Diagram

d = Diagram("C01", "Payments, styled with CSS", subtitle="brand.css: classes, kinds, edges, tokens",
            layout={"engine": "layered", "direction": "right"})
d.stylesheet("brand.css")

client = d.box("Partner API", text="REST", class_="external")
with d.group("Trusted zone", class_="trusted"):
    gateway = d.box("Gateway", text="NGINX")
    payments = d.box("Payments", text="Card capture", class_="critical")
    ledger = d.add("data", "Ledger", id="ledger")
audit = d.add("data", "Audit log", id="audit")

client >> gateway >> payments
payments.to(ledger, "write")
payments.to(audit, "event", class_="async")

diagram = d
