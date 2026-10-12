# Extending

spinagram is built from plug-ins registered through Python entry points, so a separate package can
add an output format or a layout engine.

## Backends

A backend is a class with `name` and `render(scenes, out_dir) -> list[Path]`, registered through the
`spinagram.backends` entry point:

```toml title="pyproject.toml"
[project.entry-points."spinagram.backends"]
html = "my_package.backend:HtmlBackend"
```

Backends only read the resolved `Scene`, in which every colour is hex, fonts are resolved, text is
pre-wrapped and coordinates are absolute. Adding an output format never touches layout or themes.

## Layout engines

An engine is a class with `name`, `available()` and `run(LGraph) -> LResult` (see
`spinagram.autolayout.graph`), registered through the `spinagram.layouts` entry point:

```toml title="pyproject.toml"
[project.entry-points."spinagram.layouts"]
mine = "my_package.layout:MyEngine"
```

## Python API

```python
import spinagram

diagrams = spinagram.load("specs/")                  # YAML and Python specs
spinagram.render(diagrams, "out/", theme="my-theme", formats=["svg", "pptx"], gallery=True)
scenes = spinagram.scenes(diagrams, theme="my-theme")   # resolved scenes, for custom tooling
```
