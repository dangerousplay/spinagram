"""One slide, two diagram types: an architecture view and the state machine of one of its services."""
from spinagram import Diagram

d = Diagram("B04", "Orders service and its lifecycle", subtitle="Typed regions in one diagram")

with d.group("Platform", style="soft", direction="down"):
    web = d.box("Web shop", text="React", icon="terrastruct:react")
    api = d.box("Orders API", text="Python", icon="terrastruct:python")
    db = d.box("Orders DB", text="PostgreSQL", icon="terrastruct:postgres")
web >> api >> db

with d.state_machine("Order lifecycle", direction="down") as sm:
    created = sm.state("Created")
    paid = sm.state("Paid")
    shipped = sm.state("Shipped")
    sm.initial >> created
    created.on("pay", paid)
    paid.on("ship", shipped)
    paid.on("refund", created)
    shipped >> sm.final

api.to(created, "creates")
