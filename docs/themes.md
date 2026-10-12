# Themes

A theme is a directory containing `theme.yaml` plus its assets (fonts, icons, logos). It supplies
colours, fonts, node, edge and zone styles, icons and page chrome, so the same diagram source renders
in any brand.

Start with `extends: default` and override only what differs:

```yaml title="my-theme/theme.yaml"
name: acme
extends: default
colors:
  primary: "#0F766E"
  primary-strong: "#115E59"
  primary-deep: "#134E4A"
```

Select a theme with `--theme DIR` (or a built-in name) or the `SPINAGRAM_THEME` environment
variable. In Python, pass `theme=` to `d.save(...)` or `spinagram.render(...)`.

[`src/spinagram/themes/default/theme.yaml`](https://github.com/dangerousplay/spinagram/blob/main/src/spinagram/themes/default/theme.yaml)
documents every key: `canvas`, `colors`, font roles (with font files for metrics and embedding),
`styles` for nodes, edges, zones, legends and tables, `icons`, and page chrome.

`spinagram serve` has a **Themes** tab that shows the token sheet of the active theme: colours,
fonts, styles with previews and chrome. See [Live UI](live-ui.md).
