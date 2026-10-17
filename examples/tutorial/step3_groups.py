"""Tutorial step 3: groups nest boxes into zones; the layout wraps them for you."""
from spinagram import Diagram

d = Diagram("T03", "Checkout", subtitle="Step 3: group what belongs together")

shoppers = d.box("Shoppers", icon="aws:users")
with d.group("AWS eu-west-1", style="aws-region", direction="right"):
    store = d.box("Storefront", text="CloudFront", icon="aws:cloudfront")
    with d.group("VPC", style="aws-vpc", direction="right"):
        orders = d.box("Orders API", text="FastAPI on ECS", icon="terrastruct:python")
        with d.group("Data"):
            db = d.box("Orders DB", text="PostgreSQL", icon="terrastruct:postgres")
            cache = d.box("Cache", text="Redis", icon="terrastruct:redis")
            queue = d.box("Events", text="SQS queue", icon="aws:sqs")

shoppers.to(store, "HTTPS") >> orders
orders.to(db, "SQL")
orders >> [cache, queue]
