"""The same diagram as quickstart.yaml, in Python: `python examples/quickstart.py`."""
from spinagram import Diagram

d = Diagram("Q01", "Web app on AWS", subtitle="No coordinates, laid out automatically",
            layout={"engine": "flex", "direction": "right", "gap": 60})
users = d.box("Users", icon="aws:users")
with d.group("us-east-1", style="aws-region", direction="right"):
    with d.group("VPC", style="aws-vpc", direction="right"):
        alb = d.box("Load balancer", icon="aws:alb")
        api = d.box("API", text="FastAPI on ECS", icon="terrastruct:python")
        with d.group(direction="down"):
            db = d.box("Orders DB", text="PostgreSQL", icon="terrastruct:postgres")
            cache = d.box("Cache", text="Redis", icon="terrastruct:redis")
    s3 = d.box("Uploads", text="S3 bucket", icon="aws:s3")

d.edge(users, alb, label="HTTPS")
d.chain(alb, api)
d.edge(api, db, label="SQL")
d.edge(api, cache)
d.edge(api, s3)

diagram = d  # lets `spinagram render examples/` pick it up

if __name__ == "__main__":
    d.save("out/", formats=["svg", "png", "pptx"])
