"""A Kubernetes application platform: control plane, a namespaced web app with autoscaling and a
stateful database on persistent volumes."""
from spinagram import Diagram

N = {"w": 210, "h": 84}
WIDE = {"w": 230, "h": 84}
POD = {"w": 150, "h": 60}

d = Diagram("K8S01", "Anatomy of a Kubernetes workload",
            subtitle="Ingress to pods, autoscaling, config and stateful storage in one namespace",
            layout={"engine": "flex", "direction": "right", "gap": 32, "route": "ortho",
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("k8s.css")

with d.group("Cluster · prod-eu-1", id="cluster", class_="cluster", direction="down", gap=28, padding=16):
    with d.group("Control plane", id="cp", class_="cp", direction="right", gap=64):
        api = d.box("API server", text="REST, admission", icon="k8s:api-labeled", class_="control-plane", **WIDE)
        etcd = d.box("etcd", text="3 members, Raft", icon="k8s:etcd", class_="control-plane", **N)
        sched = d.box("Scheduler", text="binds pods", icon="k8s:sched-labeled", class_="control-plane", **N)
        cm = d.box("Controllers", text="reconcile", icon="k8s:c-m-labeled", class_="control-plane", **WIDE)
    with d.group(id="workloads", class_="bare", direction="right", gap=16, align="center"):
        with d.group("namespace: shop", id="ns", class_="ns", direction="right", gap=16, align="center"):
            with d.group(id="entry", class_="bare", direction="down", gap=40):
                ing = d.box("Ingress", text="from clients, TLS", icon="k8s:ing", class_="networking", **N)
                svc = d.box("Service", text="ClusterIP :80", icon="k8s:svc", class_="networking", **N)
            with d.group(id="control", class_="bare", direction="down", gap=40):
                hpa = d.box("HPA", text="2–10 replicas", icon="k8s:hpa", class_="autoscaling", **N)
                dep = d.box("Deployment", text="rolling update", icon="k8s:deploy", class_="workload", **WIDE)
                cfg = d.box("ConfigMap", text="+ Secret", icon="k8s:cm", class_="configuration", **N)
            with d.group("ReplicaSet", id="rs", class_="pods", direction="down", gap=12):
                pods = [d.box(f"web-{s}", text="ready", icon="k8s:pod", class_="pod", id=f"pod-{s}", **POD)
                        for s in "abc"]
            with d.group(id="data", class_="bare", direction="down", gap=64):
                sts = d.box("StatefulSet", text="postgres ×3", icon="k8s:sts", class_="workload", **WIDE)
                pvc = d.box("PVC", text="50 Gi, RWO", icon="k8s:pvc", class_="storage", **N)
        pv = d.box("PV", text="gp3 StorageClass", icon="k8s:pv", class_="storage", **N)

ing >> svc
svc.to(dep, "selects")
for p in pods:
    d.edge(dep, p)
hpa.to(dep, "scales", class_="control-loop")
cfg.to(dep, "env", class_="injects-config")
pods[0].to(sts, "SQL")
sts.to(pvc, "claims")
pvc.to(pv, "bound", class_="binds-volume")
api.to(etcd, "watch", arrow="both")
d.callout(pv, "Snapshots every 6 h to object storage", title="Backups", kind="tip")
d.add_legend()

diagram = d
