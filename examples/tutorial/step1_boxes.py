"""Tutorial step 1: boxes and arrows. `spinagram serve examples/tutorial/step1_boxes.py`."""
from spinagram import Diagram

d = Diagram("T01", "Checkout", subtitle="Step 1: say what talks to what")

shoppers = d.box("Shoppers")
store = d.box("Storefront")
orders = d.box("Orders API")
db = d.box("Orders DB")

shoppers >> store >> orders >> db

diagram = d
