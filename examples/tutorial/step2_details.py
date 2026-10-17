"""Tutorial step 2: body text, icons, labelled arrows and fan-out."""
from spinagram import Diagram

d = Diagram("T02", "Checkout", subtitle="Step 2: add detail, icons and labels",
            layout={"engine": "layered", "direction": "right"})

shoppers = d.box("Shoppers", icon="aws:users")
store = d.box("Storefront", text="Next.js", icon="aws:cloudfront")
orders = d.box("Orders API", text="FastAPI", icon="terrastruct:python")
db = d.box("Orders DB", text="PostgreSQL", icon="terrastruct:postgres")
cache = d.box("Cache", text="Redis", icon="terrastruct:redis")
queue = d.box("Events", text="SQS queue", icon="aws:sqs")

shoppers.to(store, "HTTPS") >> orders
orders.to(db, "SQL")
orders >> [cache, queue]

diagram = d
