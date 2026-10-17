"""The diagram every look in this folder restyles: the code only says what each element *is*."""
from spinagram import Diagram


def platform(id: str, title: str, sheet: str) -> Diagram:
    d = Diagram(id, title, subtitle=f"The same diagram, styled by {sheet}",
                layout={"engine": "layered", "direction": "right", "rank_gap": 64, "route": "ortho"})
    d.stylesheet(sheet)
    with d.group("Event-driven shop", id="canvas", class_="canvas", direction="right"):
        with d.group("Clients", id="clients", class_="tier"):
            web = d.box("Web app", text="React", icon="terrastruct:react", class_="client")
            mobile = d.box("Mobile", text="iOS, Android", icon="selfhosted:android", class_="client")
        gateway = d.box("API gateway", text="auth, rate limits", icon="aws:api-gateway", class_="edge")
        with d.group("Services", id="services", class_="tier"):
            users = d.box("Accounts", text="Go", icon="terrastruct:go", class_="service")
            orders = d.box("Orders", text="Python", icon="terrastruct:python", class_="service hero")
            search = d.box("Search", text="Elasticsearch", icon="selfhosted:elasticsearch", class_="service")
        with d.group("Data", id="data", class_="tier"):
            db = d.box("Orders DB", text="PostgreSQL", icon="terrastruct:postgres", class_="store")
            bus = d.box("Event bus", text="Kafka on MSK", icon="aws:amazon-managed-streamingfor-apache-kafka", class_="stream")
    web >> gateway
    mobile >> gateway
    gateway >> [orders, users, search]
    orders.to(db, "SQL")
    orders.to(bus, "order.placed", class_="async")
    bus.to(search, "reindex", class_="async")
    d.add_legend({".client": "Client", ".service": "Service", ".store": "Data store", ".stream": "Event stream",
                  ".hero": "Revenue critical",
                  "edge.async": "Async event"}, position="bottom")
    return d
