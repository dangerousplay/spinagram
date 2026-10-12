"""Flowchart: `spinagram render examples/behavior/flowchart.py -f svg,pptx -o out/`."""
from spinagram import Flowchart

fc = Flowchart("B01", "Checkout", subtitle="Flowchart builder, laid out by the layered engine",
               layout={"engine": "layered", "direction": "right", "rank_gap": 48},
               css="node::title { font-size: 21 }")  # a touch smaller so all eight steps fit one slide

start = fc.start()
card = fc.io("Read card")
valid = fc.decision("Card valid?")
charge = fc.process("Charge card")
paid = fc.decision("Charged?")
receipt = fc.document("Send receipt")
error = fc.io("Show error")

start >> card >> valid
valid.yes(charge) >> paid
valid.no(error)
paid.yes(receipt) >> fc.end()
paid.no(error)
error.to(card, "retry")

diagram = fc
