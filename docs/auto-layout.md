# Automatic layout

Add `layout:` to a diagram and leave out the coordinates. Nest nodes in `groups:`, such as an AWS
Region, a VPC and its availability zones, and spinagram sizes every node from its text and icon,
places everything and draws each group as a zone with its label and corner icon.

=== "YAML"

    ```yaml
    --8<-- "examples/quickstart.yaml"
    ```

=== "Python"

    ```python
    --8<-- "examples/quickstart.py"
    ```

![Web app on AWS](assets/quickstart.svg)

## Groups

A group has an `id`, an optional `label` and `style`, and `children`: node ids or nested groups.
In YAML you can also put `in: <group-id>` on a node instead of listing it in `children`. In Python,
nodes and groups created inside `with d.group(...)` become its children.

Any zone style works: `soft`, `warning`, `alert`, `neutral`, and the AWS Architecture styles
`aws-cloud`, `aws-account`, `aws-region`, `aws-vpc`, `aws-az` and `aws-subnet`. A group without a
style is an invisible container, handy for stacking nodes (the `data` column above).

With the `flex` engine, a group takes `direction` (`right` or `down`), `columns` (grid), `gap`,
`padding` and `align`.

A larger example, Vault and Consul across three availability zones, is
[`examples/aws_layout.yaml`](https://github.com/dangerousplay/spinagram/blob/main/examples/aws_layout.yaml).

## Engines

`layout.engine` picks the engine; `layout.direction` sets the main flow (`right` or `down`).

| Engine | Needs | Strengths |
|---|---|---|
| `flex` (default) | nothing (pure Python) | Nested rows, columns and grids. Deterministic. Edges are straight, or elbowed with `route: ortho`. |
| `dot` | Graphviz (`dot` on `PATH`) | Ranked flows. Clusters for groups. Orthogonal routes (`splines=ortho`). |
| `elk` | `bun` or `node`; `elkjs` is installed into the cache on first use | Layered layout with edges routed across group borders. Orthogonal routes. |
| `d2` | `d2` on `PATH` | D2's own layouts (`options: {layout: elk\|dagre\|tala}`). |

- **Engine options:** `layout.options` is passed to the engine unchanged, as ELK properties or dot
  graph attributes.
- **Comparing engines:** `--layout ENGINE` on `render`, `check` and `facts` (or `SPINAGRAM_LAYOUT`)
  overrides the spec's engine.

```bash
spinagram render examples/aws_layout.yaml --layout elk -o out/
```

## Mixing manual and automatic placement

Nodes with explicit `x`/`y` outside any group keep their position. Laid-out content goes into
`layout.area: [x, y, w, h]`, which defaults to the canvas minus the margins and chrome. Anything that
does not fit is reported by `spinagram check`.

## Edge routes

A route from the engine becomes the edge's `via`, bound to node sides. An edge you anchored
(`a.right`) or routed (`via`) is left alone.

## Hand-tuning

Freeze the computed positions into an explicit spec, then tune it by hand:

```bash
spinagram layout spec.yaml -o frozen.yaml
```

## Your own engine

An engine is a class with `name`, `available()` and `run(LGraph) -> LResult` (see
`spinagram.autolayout.graph`), registered through the `spinagram.layouts` entry point. See
[Extending](extending.md).
