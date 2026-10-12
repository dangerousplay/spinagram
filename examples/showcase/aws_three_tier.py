"""AWS three-tier web application, after the AWS reference architecture: an automatic legend from the CSS
classes and numbered steps along the request path."""
from spinagram import Diagram

N = {"w": 196, "h": 80}  # compact cards: diagram, legend and steps share one slide

d = Diagram("AWS01", "Three-tier web application on AWS",
            subtitle="Edge, web, app and data tiers across two Availability Zones",
            layout={"engine": "flex", "direction": "right", "gap": 32, "route": "ortho",
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("aws.css")

with d.group("Internet edge", id="edge", class_="edge", direction="down", gap=22, padding=16):
    users = d.box("Users", text="web, mobile", icon="aws:users", class_="external", **N)
    dns = d.box("Route 53", text="latency DNS", icon="aws:amazon-route53", class_="edge-service", **N)
    cdn = d.box("CloudFront", text="CDN, TLS", icon="aws:cloudfront", class_="edge-service", w=216, h=80)
    waf = d.box("AWS WAF", text="managed rules", icon="aws:awswaf", class_="security", **N)
    s3 = d.box("S3", text="static origin", icon="aws:s3", class_="storage", **N)
with d.group("us-east-1", style="aws-region", padding=16):
    with d.group("VPC 10.0.0.0/16", style="aws-vpc", direction="right", align="center", gap=12, padding=16):
        alb = d.box("ALB", text="HTTPS :443", icon="aws:alb", class_="load-balancer", **N)
        with d.group(id="azs", class_="bare", direction="down", gap=20, padding=0):
            tiers = {}
            for az, n in (("a", 0), ("b", 1)):
                with d.group(f"Availability Zone {az.upper()}", style="aws-az", direction="right", gap=12, padding=16):
                    with d.group(f"Public 10.0.{n}.0/24", style="aws-subnet", class_="public", padding=14):
                        web = d.box("Web", text="Nginx · ASG", icon="aws:amazon-ec2", class_="web-tier",
                                    id=f"web-{az}", **N)
                    with d.group(f"Private 10.0.1{n}.0/24", style="aws-subnet", class_="private", padding=14):
                        app = d.box("App", text="ECS Fargate", icon="aws:amazon-elastic-container-service",
                                    class_="app-tier", id=f"app-{az}", **N)
                    with d.group(f"Data 10.0.2{n}.0/24", style="aws-subnet", class_="data", padding=14):
                        db = d.box("Aurora " + ("writer" if az == "a" else "reader"), text="PostgreSQL",
                                   icon="aws:amazon-aurora", class_="database", id=f"db-{az}", **N)
                tiers[az] = (web, app, db)

users.to(dns, "resolve", step="Users resolve the domain")
dns.to(cdn, "alias", step="Route 53 aliases to CloudFront")
cdn.to(waf, step="AWS WAF filters each request")
waf.to(alb, step="The ALB balances across zones")
for az, (web, app, db) in tiers.items():
    alb >> web
    if az == "a":
        web.to(app, step="Web tier calls the app tier")
        app.to(db, "SQL", step="App tier writes to Aurora")
    else:
        web >> app
        app.to(db, "SQL")
d.edge(tiers["a"][2], tiers["b"][2], "replication", class_="replication")
d.add_legend()

diagram = d
