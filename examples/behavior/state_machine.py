"""State machine: composite state, orthogonal regions, history, choice and self-transition."""
from spinagram import StateMachine

sm = StateMachine("B02", "Order lifecycle", subtitle="StateMachine builder", direction="right",
                  layout={"engine": "layered", "direction": "right", "rank_gap": 56},
                  css="state::title { font-size: 21 } state::body { font-size: 16 }")

created = sm.state("Created", entry="reserve stock")
paid = sm.state("Paid", do="notify warehouse")
cancelled = sm.state("Cancelled")
sm.initial >> created
created.on("pay", paid, guard="amount ok", action="capture")
created.on("cancel", cancelled)
paid.on("retry", paid)

with sm.composite("Fulfilment") as f:
    with f.region() as picking:
        pick = picking.state("Picking")
        picking.initial >> pick
    with f.region() as billing:
        bill = billing.state("Invoicing")
        billing.initial >> bill

paid.on("ship", pick)
done = sm.choice()
bill >> done
done.to(sm.final, "[delivered]")
done.to(cancelled, "[lost]")
cancelled >> sm.final

diagram = sm
