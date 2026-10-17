"""Tutorial step 5: classes and a stylesheet give the diagram your brand."""
from spinagram import Diagram

d = Diagram("T05", "Checkout", subtitle="Step 5: style it with CSS")
d.stylesheet("checkout.css")

shoppers = d.box("Shoppers", icon="aws:users", class_="external")
with d.group("AWS eu-west-1", style="aws-region", direction="right"):
    store = d.box("Storefront", text="CloudFront", icon="aws:cloudfront")
    with d.group("VPC", style="aws-vpc", direction="right"):
        orders = d.box("Orders API", text="FastAPI on ECS", icon="terrastruct:python", class_="critical")
        with d.group("Data", gap=24):
            db = d.box("Orders DB", text="PostgreSQL", icon="terrastruct:postgres")
            cache = d.box("Cache", text="Redis", icon="terrastruct:redis")
            queue = d.box("Events", text="SQS queue", icon="aws:sqs")

shoppers.to(store, "HTTPS") >> orders
orders.to(db, "SQL")
orders >> cache
orders.to(queue, "order.placed", class_="async")

d.add_legend({".external": "Outside our account", ".critical": "Revenue critical",
              "edge.async": "Async event"}, position="bottom")

if __name__ == "__main__":
    d.save("out/", formats=["svg", "png", "pptx"])
