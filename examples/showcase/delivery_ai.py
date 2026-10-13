"""A delivery platform with an AI gateway: GitLab builds and SonarQube gates, Artifactory and Harbor hold the
artifacts, Argo CD deploys to Kubernetes with secrets from Vault, and apps reach Claude, OpenAI and a local Ollama
through one gateway. Logos from the `logos`, `cncf`, `ai` and `selfhosted` packs; the dark tiles draw each pack's
dark-fill artwork."""
from spinagram import Diagram

N = {"w": 260, "h": 96}
DARK = {"style": "dark"}  # dark fill (delivery_ai.css) + the icons' dark-fill artwork

d = Diagram("AI01", "Delivery platform with an AI gateway",
            subtitle="From merge request to running pod, and one governed door to the models",
            layout={"engine": "flex", "direction": "right", "rank_gap": 40, "route": "ortho",
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("delivery_ai.css")

with d.group("Build", id="build", direction="down", gap=22, padding=16):
    scm = d.box("GitLab", text="merge requests, CI", icon="logos:gitlab", **N)
    quality = d.box("SonarQube", text="quality gate", icon="selfhosted:sonarqube", **N)
with d.group("Supply", id="supply", direction="down", gap=22, padding=16):
    jfrog = d.box("Artifactory", text="Maven, npm, PyPI", icon="logos:jfrog", **N)
    harbor = d.box("Harbor", text="signed images", icon="cncf:harbor", **DARK, **N)
    vault = d.box("Vault", text="secrets", icon="logos:vault", **N)
with d.group("Run", id="run", direction="down", gap=22, padding=16):
    argo = d.box("Argo CD", text="GitOps sync", icon="cncf:argo", **N)
    k8s = d.box("Kubernetes", text="workloads", icon="cncf:kubernetes", **DARK, **N)
    gw = d.box("AI gateway", text="keys, quotas, audit", icon="ai:mcp", **DARK, **N)
with d.group("Models", id="models", class_="ai", direction="down", gap=22, padding=16):
    claude = d.box("Claude", text="Anthropic", icon="ai:claude", **N)
    openai = d.box("OpenAI", text="GPT models", icon="ai:openai", **DARK, **N)
    ollama = d.box("Ollama", text="local models", icon="ai:ollama", **N)

scm.to(quality, step="Every merge request runs the quality gate")
scm.to(jfrog, step="Libraries go to Artifactory")
scm.to(harbor, step="Images are pushed to Harbor")
harbor.to(argo)
argo.to(k8s, step="Argo CD syncs the cluster from Git")
vault.to(k8s)
k8s.to(gw, step="Apps call models through the gateway")
gw.to([claude, openai, ollama])
d.add_legend()

diagram = d
