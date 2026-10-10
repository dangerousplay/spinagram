# Tasks — pptx-svg + auto-layout

Gate for every task: `uv run pytest -q` green (existing 30 + new).

| # | Task | Where | Depends | Reqs | Done when | Status |
|---|---|---|---|---|---|---|
| T1 [P] | PPTX SVG pictures (svgBlip + resvg fallback + dedupe + opt-out) | backends/pptx.py, tests | – | PSVG-01..07 | zip has svg+png parts, XML has svgBlip; tests per icon path | done |
| T2 | Model: `Group`, `Diagram.groups/layout`, `d.group()` ctx, YAML `groups:` tree + node `in:`, validation | model.py, yaml_io.py | – | LAY-01, LAY-02 | YAML≡DSL test; errors for unknown/dup/cycle | done |
| T3 | Sizing + LGraph build + engine protocol/registry | layout/{__init__,sizing,graph}.py, engines/__init__.py | T2 | LAY-03, LAY-10 | toy engine test; auto sizes test | done |
| T4 | flex engine | engines/flex.py | T3 | LAY-11 | invariant suite passes for flex | done |
| T5 | Place + writeback + `api.scenes` hook + QA overflow | layout/{place,writeback}.py, api.py, qa.py | T3, T4 | LAY-04..06, LAY-20, LAY-22 | AWS example renders via flex, check 0 issues; old specs byte-identical | done |
| T6 [P] | dot adapter | engines/dot.py | T5 | LAY-12, LAY-15, LAY-16 | invariants + routes; skip w/o dot | done |
| T7 [P] | elk adapter + runner + first-use install | engines/elk.py, elk_runner.mjs | T5 | LAY-13, LAY-15, LAY-16 | invariants + orthogonal routes; skip w/o bun/node | done |
| T8 [P] | d2 adapter | engines/d2.py | T5 | LAY-14, LAY-15 | invariants; skip w/o d2 | done |
| T9 | flex ortho elbow | layout/writeback.py | T5 | LAY-21 | elbow test | done |
| T10 | CLI `--layout`, `diagramkit layout` freeze + `yaml_io.dump` | cli.py, yaml_io.py | T5 | LAY-30, LAY-31 | frozen ≡ auto render | done |
| T11 | Example + README + skill docs + theme defaults | examples/, README, skills/, themes | T6–T10 | LAY-32 | example renders with all engines; PNGs reviewed | done |
