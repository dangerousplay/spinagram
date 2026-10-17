"""Three diagram types on one slide: the payments architecture, the fraud-check flowchart its API runs
and the lifecycle of a payment. Each region has its own layout; arrows connect them like any boxes."""
from spinagram import Diagram

d = Diagram("M01", "Payments, end to end", subtitle="Architecture, flowchart and state machine on one slide",
            layout={"engine": "flex", "direction": "right", "gap": 56})
d.stylesheet("mixed.css")

with d.flowchart("Fraud check", id="fraud", class_="flow") as fc:
    start = fc.start()
    score = fc.process("Score risk")
    risky = fc.decision("Score > 80?")
    review = fc.process("Manual review")
    ok = fc.end("Approve")
    start >> score >> risky
    risky.yes(review) >> ok
    risky.no(ok)

with d.group("Architecture", id="arch", class_="arch", direction="down"):
    shop = d.box("Checkout", text="web and mobile", icon="terrastruct:react")
    api = d.box("Payments API", text="Python", icon="terrastruct:python", class_="hero")
    psp = d.box("Card network", text="Stripe", icon="selfhosted:stripe")
shop.to(api, "pay")
api.to(psp, "charge")

with d.state_machine("Payment", id="payment", class_="states") as sm:
    pending = sm.state("Pending")
    captured = sm.state("Captured")
    refunded = sm.state("Refunded")
    failed = sm.state("Failed")
    sm.initial >> pending
    pending.on("capture", captured)
    pending.on("decline", failed)
    captured.on("refund", refunded)
    refunded >> sm.final
    failed >> sm.final

api.to(score, "runs", class_="link")
ok.to(pending, "creates", class_="link")

diagram = d
