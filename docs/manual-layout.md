# Manual layout

Without `layout:`, every node has explicit coordinates on a 1920×1080 canvas (the default theme's
size). Use this for slides where every pixel matters, or start from automatic layout and
[freeze it](auto-layout.md#hand-tuning).

=== "YAML"

    ```yaml
    id: D01
    title: How a change is routed
    subtitle: Facts decide the path
    nodes:
      - {id: req, x: 80, y: 220, w: 420, h: 300, title: Change request, text: Created by the source tool, icon: document}
      - {id: eng, x: 600, y: 220, w: 420, h: 300, style: dark, title: Risk engine}
      - {id: cab, kind: diamond, x: 1120, y: 260, w: 260, h: 220, title: [Business, impact?]}
    edges:
      - req -> eng
      - "eng -> cab: classify"
      - {from: cab.bottom, to: [1250, 700], color: alert, dashed: true}
    ```

=== "Python"

    ```python
    from spinagram import Diagram

    d = Diagram("D01", "How a change is routed", subtitle="Facts decide the path")
    req, eng, out = d.row(["Change request", "Risk engine", "Route"], x=80, y=220, w=420, h=300, gap=80,
                          styles=["default", "dark", "default"])
    d.edge(req, eng)
    d.edge(eng.right, out.left, label="classify")
    d.save("out/", theme="path/to/theme", formats=["svg", "pptx"])
    ```

## Nodes

| Kind | YAML | Python |
|---|---|---|
| Box | `kind: box` (default) | `d.box(title, ...)` |
| Note | `kind: note` | `d.note(title, ...)` |
| Diamond | `kind: diamond` | `d.diamond(title, ...)` |
| Pill (centred on x, y) | `kind: pill` | `d.pill(title, x=, y=)` |
| Free text (x, y is the first baseline) | `kind: text` | `d.label(text, x=, y=)` |

Position a node with `x`, `y`, `w`, `h`, or the YAML shorthand `at: [x, y, w, h]`.
Common fields: `title`, `text`, `icon`, `style` (`default`, `dark`, `soft`, `warning`, `alert`,
`neutral` or any style from your theme). Python helpers `d.row(...)` and `d.column(...)` place a
sequence of boxes, and `d.chain(a, b, c)` links them.

## Edges

The shorthand is `"<from> -> <to>[: label]"`; `<-`, `<->` and `--` (no arrow) work too. An endpoint is either:

- a node id: the facing side is picked automatically, or
- `node.side[@frac]`: `side` is one of `top|bottom|left|right|center` and `frac` a position from 0
  to 1 along that side, or
- a point `[x, y]`.

The long form takes `from`, `to`, `label`, `color`, `dashed` and `via` (a list of waypoints).

## Zones, tables and legends

```yaml
zones:
  - {x: 60, y: 180, w: 1800, h: 380, label: Automatic, color: soft}
legend:
  x: 100
  y: 640
  items:
    - {color: default, label: automatic}
    - {color: warning, label: review}
```

```python
d.zone("Production", x=60, y=200, w=900, h=500, color="soft")
d.table(["Signal", "Source", "Effect"],
        [["Chaos test failed", "Stress cluster", "Window or approval"]],
        x=80, y=760, widths=[400, 400, 600])
d.set_legend([("primary", "Automated"), ("warning", "Manual")], x=80, y=960)
```

See [`examples/decision.yaml`](https://github.com/dangerousplay/spinagram/blob/main/examples/decision.yaml) for zones and a legend, and
[`examples/release_flow.py`](https://github.com/dangerousplay/spinagram/blob/main/examples/release_flow.py) for a table.
