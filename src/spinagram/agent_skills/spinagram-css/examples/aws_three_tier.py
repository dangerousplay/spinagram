"""AWS three-tier web application, after the AWS reference architecture."""
from spinagram import Diagram

N = {"w": 218, "h": 84}  # compact cards: the whole architecture fits one slide

d = Diagram("AWS01", "Three-tier web application on AWS",
            subtitle="Edge, web, app and data tiers across two Availability Zones",
            layout={"engine": "flex", "direction": "right", "gap": 56, "route": "ortho"})
d.stylesheet("showcase.css")
d.stylesheet("aws.css")

with d.group("Internet edge", id="edge", class_="edge", direction="down", gap=24):
    users = d.box("Users", text="web, mobile", icon="aws:users", class_="client", **N)
    dns = d.box("Route 53", text="latency DNS", icon="aws:amazon-route53", class_="edge-svc", **N)
    cdn = d.box("CloudFront", text="CDN, TLS", icon="aws:cloudfront", class_="edge-svc", **N)
    waf = d.box("AWS WAF", text="managed rules", icon="aws:awswaf", class_="security", **N)
    s3 = d.box("S3", text="CloudFront origin", icon="aws:s3", class_="store", **N)
with d.group("us-east-1", style="aws-region"):
    with d.group("VPC 10.0.0.0/16", style="aws-vpc", direction="right", align="center", gap=40):
        alb = d.box("ALB", text="HTTPS :443", icon="aws:alb", class_="lb", **N)
        with d.group(id="azs", class_="bare", direction="down", gap=24, padding=0):
            tiers = {}
            for az, n in (("a", 0), ("b", 1)):
                with d.group(f"Availability Zone {az.upper()}", style="aws-az", direction="right", gap=28):
                    with d.group(f"Public 10.0.{n}.0/24", style="aws-subnet", class_="public"):
                        web = d.box("Web", text="Nginx · ASG", icon="aws:amazon-ec2", class_="web", id=f"web-{az}", **N)
                    with d.group(f"Private 10.0.1{n}.0/24", style="aws-subnet", class_="private"):
                        app = d.box("App", text="ECS Fargate", icon="aws:amazon-elastic-container-service",
                                    class_="app", id=f"app-{az}", **N)
                    with d.group(f"Data 10.0.2{n}.0/24", style="aws-subnet", class_="data"):
                        db = d.box("Aurora " + ("writer" if az == "a" else "reader"), text="PostgreSQL",
                                   icon="aws:amazon-aurora", class_="db", id=f"db-{az}", **N)
                tiers[az] = (web, app, db)

users.to(dns, "resolve")
dns.to(cdn, "alias")
cdn >> waf
waf.to(alb)
for az, (web, app, db) in tiers.items():
    alb >> web >> app
    app.to(db, "SQL")
d.edge(tiers["a"][2], tiers["b"][2], "replication", class_="replication")

diagram = d
