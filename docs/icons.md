# Icon packs

Vendor icon sets are downloaded on first use into `~/.cache/spinagram/icons` (override with
`SPINAGRAM_CACHE`; set `SPINAGRAM_OFFLINE=1` to never download) and referenced as `pack:name`:

```yaml
nodes:
  - {id: db, title: Orders DB, icon: "aws:rds"}
  - {id: gke, title: Cluster, icon: "gcp:gke"}
```

| Pack | Source | Format |
|---|---|---|
| `aws` | AWS Architecture Icons via the npm package `aws-icons` | SVG |
| `gcp` | Google Cloud official icons | SVG |
| `azure` | Azure public service icons V21 | SVG |
| `k8s` | kubernetes/community icons (`-labeled` variants too) | SVG |
| `oci` | Oracle Cloud icons from mingrammer/diagrams (dark variant on dark fills) | PNG |
| `openstack` | OpenStack project icons from mingrammer/diagrams | PNG |
| `terrastruct` | Terrastruct/D2 icon sheet: languages, databases, frameworks, dev tools, generic infra + cloud subset | SVG |

Names are kebab-case file names (`aws:amazon-ec2`), with short aliases (`aws:ec2`, `aws:s3`,
`aws:alb`, `gcp:gke`, `azure:aks`, …). For general software architecture use `terrastruct`:
technologies by plain name (`terrastruct:python`, `terrastruct:postgres`, `terrastruct:redis`,
`terrastruct:kafka`, `terrastruct:sqs`), generic glyphs by category (`terrastruct:tech-server`,
`terrastruct:infra-firewall`, `terrastruct:db`). See
[`examples/software_architecture.yaml`](https://github.com/dangerousplay/spinagram/blob/main/examples/software_architecture.yaml).

An `icon` can also be a file path, resolved relative to the spec.

## Managing packs

```bash
spinagram icons list                       # packs, version, download state
spinagram icons fetch aws k8s              # pre-download (default: all)
spinagram icons search load balancer       # find names in downloaded packs
spinagram icons add brand --dir ~/brand/icons                     # local folder
spinagram icons add tabler --npm @tabler/icons@3.19.0 --include 'package/icons/outline/*'
spinagram icons add mine --github org/repo@v1.2 --include 'svg/*' --project   # ./spinagram-icons.yaml
spinagram icons add corp --npm @team/icons@1.0.0 --registry https://artifactory.example/api/npm/npm-virtual/
spinagram icons import node_modules/@team/icons/spinagram-icons.yaml   # a package can ship its own descriptor
spinagram icons remove brand
```

## Pack format

A pack is YAML (built-ins live in `src/spinagram/icon_packs/`):

- `source`: a `zip` URL, an `npm` package, a `github` repo/ref, a `listing` (an index page: `url` +
  `pattern` regex naming each file), or a local `dir`, plus `include` globs.
- `rules`: regex → name template, with optional `tone: dark` and `aliases`.
- `strip`: regexes that derive short aliases.
- `alias`: a curated alias map.

Registries merge built-in < `~/.config/spinagram/icons.yaml` < `./spinagram-icons.yaml` <
`$SPINAGRAM_ICON_PACKS`. A theme can map its own names onto packs:
`icons: {alias: {ec2: "aws:ec2"}}`.

Vendor artwork keeps its owner's terms (each pack lists `license` and `homepage`).

## PNG → SVG icons

With the `vector` extra installed, PNG icons are traced into SVG automatically: theme icons, icons
referenced by path and PNG icon packs (`oci`, `openstack`). A traced icon is only used when it is
faithful: it is rendered back with resvg at the source size and compared over grey (mean Δ ≤ 8 and
≤ 1 % of pixels off by more than 128); photos and heavy gradients stay PNG. Results are cached by
content hash. PowerPoint gets the SVG with the original PNG as its fallback.

```bash
spinagram vectorize icons/ -o vector/      # batch, with a score table (--force writes rejects too)
SPINAGRAM_VECTORIZE=0 spinagram render …   # turn it off; or icons: {vectorize: false} in a theme / pack
```
