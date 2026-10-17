"""Tutorial step 4: numbered steps, a callout and a legend explain the diagram on the slide."""
from spinagram import Diagram

d = Diagram("T04", "Checkout", subtitle="Step 4: explain it with steps, callouts and a legend")

shoppers = d.box("Shoppers", icon="aws:users")
with d.group("AWS eu-west-1", style="aws-region", direction="right"):
    store = d.box("Storefront", text="CloudFront", icon="aws:cloudfront")
    with d.group("VPC", style="aws-vpc", direction="right"):
        orders = d.box("Orders API", text="FastAPI on ECS", icon="terrastruct:python")
        with d.group("Data"):
            db = d.box("Orders DB", text="PostgreSQL", icon="terrastruct:postgres")
            cache = d.box("Cache", text="Redis", icon="terrastruct:redis")
            queue = d.box("Events", text="SQS queue", icon="aws:sqs")

shoppers.to(store, "HTTPS", step="Shopper opens the cart")
store.to(orders, step="Storefront posts the order")
orders.to(db, "SQL", step="Order is stored")
orders >> cache
orders.to(queue, step="Fulfilment is notified")

d.callout(shoppers, "40k checkouts an hour on sale days", title="Peak load", kind="warning", side="bottom")
d.add_legend({"aws:users": "People", "terrastruct:python": "Service", "aws:sqs": "Async messaging"})

diagram = d
