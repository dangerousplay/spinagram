"""Automatic layout: no coordinates. Run `python examples/quickstart.py`, or
`spinagram render examples/quickstart.py -f svg,png,pptx -o out/`."""
from spinagram import Diagram

d = Diagram("Q01", "Web app on AWS", subtitle="No coordinates, laid out automatically")

users = d.box("Users", icon="aws:users")
with d.group("us-east-1", style="aws-region", direction="right"):
    with d.group("VPC", style="aws-vpc", direction="right"):
        lb = d.box("Load balancer", icon="aws:alb")
        api = d.box("API", text="FastAPI on ECS", icon="terrastruct:python")
        with d.group():  # no style: a light "soft" zone
            db = d.box("Orders DB", text="PostgreSQL", icon="terrastruct:postgres")
            cache = d.box("Cache", text="Redis", icon="terrastruct:redis")
    s3 = d.box("Uploads", text="S3 bucket", icon="aws:s3")

users.to(lb, "HTTPS") >> api
api.to(db, "SQL")
api >> [cache, s3]

diagram = d  # lets `spinagram render` and `spinagram serve` pick it up

if __name__ == "__main__":
    d.save("out/", formats=["svg", "png", "pptx"])
