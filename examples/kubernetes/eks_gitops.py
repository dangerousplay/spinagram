"""GitOps delivery to EKS as an activity with swimlanes: GitHub Actions builds and signs the image, Argo CD
syncs the change, Karpenter adds capacity while the rollout runs, and Prometheus gates the result."""
from spinagram import Activity

A = {"w": 168, "h": 62}

act = Activity("EKS03", "Shipping a change with GitOps",
               subtitle="GitHub Actions · ECR · Argo CD · Karpenter · Prometheus, as swimlanes",
               direction="right", category="Kubernetes", tags=["aws", "kubernetes", "gitops"],
               layout={"engine": "layered", "direction": "right", "rank_gap": 34, "gap": 22})
act.stylesheet("gitops.css")

with act.sequence():
    with act.lane("GitHub Actions"):
        act.start()
        act.action("Build and sign image", **A)
        act.send("Push to ECR", **A)
    with act.lane("Argo CD"):
        act.receive("Detect new tag", **A)
        act.action("Sync manifests", **A)
    with act.lane("EKS cluster"):
        with act.parallel() as par:
            with par.branch():
                act.action("Karpenter adds nodes", **A)
            with par.branch():
                act.action("Rolling update", **A)
    with act.lane("Prometheus"):
        check = act.decision("Error rate OK?", **A)
with act.lane("Prometheus"):
    done = act.end()
with act.lane("Argo CD"):
    rollback = act.action("Roll back", id="rollback", **A)
check.to(done, "yes")
check.to(rollback, "no")

diagram = act
