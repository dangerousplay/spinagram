"""Activity: swimlanes, a sequence and a parallel block (fork and join bars)."""
from spinagram import Activity

act = Activity("B03", "Order fulfilment", subtitle="Activity builder with swimlanes", direction="right",
               layout={"engine": "layered", "direction": "right", "rank_gap": 44})

with act.sequence():
    with act.lane("Customer"):
        act.start()
        act.action("Place order")
    with act.lane("Shop"):
        act.action("Check stock")
        with act.parallel() as par:
            with par.branch():
                act.action("Pick items")
                pack = act.action("Pack")
            with par.branch():
                act.action("Send invoice")
    with act.lane("Warehouse"):
        act.send("Ship parcel")
        act.end()

with act.lane("Shop"):
    slip = act.object("Packing slip")
pack >> slip

diagram = act
