"""Illustrative notes: decision cards with an accent bar, a quote, and sticky notes for open questions."""
from spinagram import Diagram

d = Diagram("NOTE01", "Architecture decisions", subtitle="Why the three-tier platform looks the way it does",
            category="Decisions", tags=["adr", "aws"])
d.stylesheet("showcase.css")
d.stylesheet("notes.css")

CARD = {"w": 540, "h": 210}
d.note("Aurora PostgreSQL", text="Managed backups and point-in-time recovery; a reader in a second zone takes "
       "reporting load off the writer.", variant="card", icon="aws:amazon-aurora", x=80, y=200, **CARD)
d.note("ECS on Fargate", text="No hosts to patch; tasks scale on CPU and queue depth, and deploys roll per "
       "zone.", variant="card", icon="aws:amazon-elastic-container-service", x=690, y=200, **CARD)
d.note("CloudFront and WAF", text="Static assets and TLS at the edge; managed rules stop the noisy part of "
       "the internet before it reaches the VPC.", variant="card", icon="aws:cloudfront", x=1300, y=200, **CARD)
d.note("Werner Vogels", text="Everything fails, all the time. Build for it.", variant="quote",
       x=80, y=520, w=1150, h=300, class_="hero-quote")
d.note("Open question", text="Do we need a second region before the EU launch?", x=1300, y=520, w=540, h=140,
       class_="question")
d.note("Next review", text="Revisit the cache strategy after Q3 load tests.", x=1300, y=680, w=540, h=140,
       class_="question")

diagram = d
