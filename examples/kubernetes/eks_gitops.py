"""GitOps delivery to EKS as an activity with swimlanes: GitHub Actions builds and signs the image, Argo CD
syncs the change, Karpenter adds capacity while the rollout runs, and Prometheus gates the result."""
from spinagram import Activity

act = Activity("EKS03", "Shipping a change with GitOps", node_size=(168, 62),
               subtitle="GitHub Actions · ECR · Argo CD · Karpenter · Prometheus, as swimlanes",
               direction="right", category="Kubernetes", tags=["aws", "kubernetes", "gitops"],
               layout={"engine": "layered", "direction": "right", "rank_gap": 34, "gap": 22})
act.stylesheet("gitops.css")

with act.sequence():
    with act.lane("GitHub Actions"):
        act.start()
        act.action("Build and sign image")
        act.send("Push to ECR")
    with act.lane("Argo CD"):
        act.receive("Detect new tag")
        act.action("Sync manifests")
    with act.lane("EKS cluster"):
        with act.parallel() as par:
            with par.branch():
                act.action("Karpenter adds nodes")
            with par.branch():
                act.action("Rolling update")
    with act.lane("Prometheus"):
        check = act.decision("Error rate OK?")
with act.lane("Prometheus"):
    done = act.end()
with act.lane("Argo CD"):
    rollback = act.action("Roll back", id="rollback")
check.to(done, "yes")
check.to(rollback, "no")
