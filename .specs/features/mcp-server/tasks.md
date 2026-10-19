# MCP server — Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline. New package `spinagram.mcp_server`: `tools.py` (plain functions over the existing API, no MCP import), `server.py` (MCP binding with the official SDK v2 `MCPServer`), `install.py` (agent config writers). CLI wiring in `cli.py` like `serve`.
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase and spec. Guidelines found: `pyproject.toml` (pytest, ruff; no coverage threshold), `.github/workflows/ci.yml` (`uv sync --locked --all-extras`, `uv run pytest -q`; no Chromium in CI), `tests/test_skills.py` (CLI tests call `cli.main` with `tmp_path`). Strong defaults applied.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
|---|---|---|---|---|
| `mcp_server.tools` | unit | 1:1 to MCP-02, 05..11 + edge cases | `tests/test_mcp_tools.py` | `uv run --all-extras pytest -q tests/test_mcp_tools.py` |
| `mcp_server.server` | integration (in-process `mcp.Client`) | MCP-01, 03, 04, 10, 13..16 | `tests/test_mcp_server.py` | `uv run --all-extras pytest -q tests/test_mcp_server.py` |
| `mcp_server.install` | unit (`tmp_path` homes) | INST-01..09 per agent, both scopes | `tests/test_mcp_install.py` | `uv run --all-extras pytest -q tests/test_mcp_install.py` |
| CLI (`cli.py` `mcp`, `mcp install`) | integration (`cli.main`, subprocess for HTTP) | MCP-12, HTTP-01/02, INST-01/03/08/09/10 messages and exit codes | `tests/test_mcp_cli.py` | `uv run --all-extras pytest -q tests/test_mcp_cli.py` |
| `__main__.py`, extras | unit (subprocess) | `python -m spinagram` runs the CLI | `tests/test_mcp_cli.py` | same |
| Skill docs | none | build gate only | - | build gate |

## Gate Check Commands

| Gate Level | When to Use | Command |
|---|---|---|
| Quick | Tasks with unit/integration tests | `uv run --all-extras pytest -q tests/test_mcp_tools.py tests/test_mcp_server.py tests/test_mcp_install.py tests/test_mcp_cli.py` |
| Build | Phase end, docs, dependency changes | `uv run ruff check src tests examples && uv run --all-extras pytest -q` |

---

## Execution Plan

### Phase 1: Server and install

```
T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8
```

### Phase 2: Verifier fixes (validation.md, iteration 1)

```
T9 → T10 → T11 → T12 → T13
```

### Phase 3: Verifier fixes (validation.md, iteration 2)

```
T14 → T15 → T16
```

### Phase 4: Verifier fixes (validation.md, iteration 3; 4th pass approved by the user)

```
T17
```

### Phase 5: Pass-4 gaps (user: add the tests and release without a 5th pass)

```
T18
```

---

## Task Breakdown

### T1: `python -m spinagram` and the `mcp` extra [x]

**What**: `spinagram/__main__.py` runs `cli.main`; `pyproject.toml` gains `mcp = ["mcp>=2.3,<3"]`, added to `all`; `uv.lock` updated.
**Where**: `src/spinagram/__main__.py`
**Depends on**: None
**Requirement**: INST-05 (launch command)

**Done when**:

- [x] Test: `[sys.executable, "-m", "spinagram", "-V"]` prints the version, exit 0
- [x] Build gate passes

**Tests**: unit
**Gate**: build
**Commit**: `build(mcp): add the mcp extra and python -m spinagram`

---

### T2: Tool functions [x]

**What**: `Tools(root, theme, layout, formats)` with `render`, `check`, `layout`, `styles`, `icons_search`, `previews`; root confinement; errors as `ValueError`/`KeyError` with the CLI messages.
**Where**: `src/spinagram/mcp_server/tools.py`
**Depends on**: T1
**Reuses**: `cli._collect`, `api.render`, `api.scenes`, `qa.check`, `css.inspect`/`css.select`, `icons.search`
**Requirement**: MCP-02, MCP-05, MCP-06, MCP-07, MCP-08, MCP-09, MCP-11

**Done when**:

- [x] Tests: each tool's output equals what the CLI prints for the same input; out-of-root paths, `..`, absolute `out` and symlinks → `path outside root`; relative `out` under root; empty paths → `no diagrams found`; server defaults vs per-call overrides

**Tests**: unit
**Gate**: quick
**Commit**: `feat(mcp): add spinagram tool functions confined to a root`

---

### T3: MCP server binding [x]

**What**: `build(tools) -> MCPServer` registering the five tools, PNG previews (≤4, `Image`), the preview notes, `ToolError` for failures, skill resources, stderr log line per call, one write lock.
**Where**: `src/spinagram/mcp_server/server.py`
**Depends on**: T2
**Requirement**: MCP-01, MCP-03, MCP-04, MCP-10, MCP-13, MCP-14, MCP-15, MCP-16

**Done when**:

- [x] Integration tests via `mcp.Client(server)`: tool names; render result + images (stubbed renderer: 5 diagrams → 4 images in order); missing png → note; error result text; log lines; resources list/read; concurrent renders serialised

**Tests**: integration
**Gate**: quick
**Commit**: `feat(mcp): serve the tools and skills over mcp`

---

### T4: `spinagram mcp` command [x]

**What**: CLI subcommand: `-t`, `--layout`, `--formats`, `--root`, `--http PORT`, `--host`; missing extra message; non-loopback warning.
**Where**: `src/spinagram/cli.py`
**Depends on**: T3
**Requirement**: MCP-12, HTTP-01, HTTP-02

**Done when**:

- [x] Tests: missing `mcp` import → stderr message, exit 2; `--http` on a free port answers `check` through an HTTP `mcp.Client`; `--host 0.0.0.0` prints the warning

**Tests**: integration
**Gate**: quick
**Commit**: `feat(cli): add spinagram mcp with stdio and http transports`

---

### T5: Agent config writers (JSON) [x]

**What**: `AGENTS` table, `entry(agent, scope, args|url)` and `install(agent, user, name, entry, force, base, home)` for claude, cursor, gemini, copilot, opencode: create, merge, keep other keys, refuse duplicates, `--force`, parse errors.
**Where**: `src/spinagram/mcp_server/install.py`
**Depends on**: T4
**Requirement**: INST-01, INST-02, INST-04, INST-05, INST-06, INST-07, INST-08, INST-09

**Done when**:

- [x] Tests per agent × scope: file path, key, exact entry (stdio, `--uvx`, `--url`); other servers and keys survive; duplicate → `FileExistsError` and unchanged bytes; force replaces only the entry; bad JSON → error, unchanged

**Tests**: unit
**Gate**: quick
**Commit**: `feat(mcp): write mcp entries into agent json configs`

---

### T6: Codex TOML writer [x]

**What**: `[mcp_servers.<name>]` table appended or replaced as text; rest of the file byte-identical; `tomllib` parse check.
**Where**: `src/spinagram/mcp_server/install.py`
**Depends on**: T5
**Requirement**: INST-01, INST-02, INST-06, INST-07, INST-08, INST-09

**Done when**:

- [x] Tests: new file; existing file with other tables (text outside the table unchanged); duplicate; force; `url` entry; invalid TOML → error, unchanged

**Tests**: unit
**Gate**: quick
**Commit**: `feat(mcp): write codex toml entries`

---

### T7: `spinagram mcp install` command [x]

**What**: CLI: `-a` (repeatable, required), `--user`, `--name`, `--force`, `--uvx`, `--url`, `-t`, `--root`, `--formats`, `--layout`; messages and exit codes.
**Where**: `src/spinagram/cli.py`
**Depends on**: T6
**Requirement**: INST-01, INST-03, INST-04, INST-08, INST-09, INST-10

**Done when**:

- [x] Tests: `installed <name> in <file>` per agent; two `-a` → two files; flags appear in args with absolute root; duplicate → exit 1 + message; bad file → exit 2 + message; unknown/missing agent → exit 2 listing agents

**Tests**: integration
**Gate**: build
**Commit**: `feat(cli): add spinagram mcp install for coding agents`

---

### T8: Document the server in the skill [x]

**What**: `## MCP server` section: tools, install examples, root rule, previews.
**Where**: `src/spinagram/agent_skills/spinagram/SKILL.md`
**Depends on**: T7
**Requirement**: DOC-01

**Done when**:

- [x] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `docs(skills): document the spinagram mcp server`

---

### T9: Server theme outside the root (gap 1, bug) [x]

**What**: `Tools` resolves the server `-t` once against the start cwd and never root-checks it; per-call theme paths stay confined; `install` stores an existing `-t` folder as absolute.
**Where**: `src/spinagram/mcp_server/tools.py`
**Depends on**: None (Phase 1 done)
**Requirement**: MCP-11, INST-04

**Done when**:

- [x] Tests: a theme folder outside the root works as the server default (absolute and relative-to-cwd); `server_args` makes an existing `-t` absolute and keeps a built-in name

**Tests**: unit
**Gate**: quick
**Commit**: `fix(mcp): let the server theme live outside the root`

---

### T10: Layout default on every tool (gap 2) [x]

**What**: Tests that `check` and `layout` use the server `--layout` (`styles` takes no layout) and a per-call value wins (kills M5).
**Where**: `tests/test_mcp_tools.py`
**Depends on**: T9
**Requirement**: MCP-11

**Done when**:

- [x] Ignoring the default layout in `scenes` or `layout_yaml` fails a test

**Tests**: unit
**Gate**: quick
**Commit**: `test(mcp): require the server layout default on every tool`

---

### T11: JSON text and TOML comments (gaps 3, 4) [x]

**What**: JSON is written with indent 2 and a final newline (exact text asserted); a Codex `--force` keeps comment lines that sit above the next table.
**Where**: `src/spinagram/mcp_server/install.py`
**Depends on**: T10
**Requirement**: INST-07

**Done when**:

- [x] Tests: exact written JSON text; comment above the next table survives `--force`

**Tests**: unit
**Gate**: quick
**Commit**: `fix(mcp): keep comments above the next codex table on replace`

---

### T12: Server key that is not an object (gap 5) [x]

**What**: `{"mcpServers": []}` (or any non-object under the key) → `cannot parse <file>: <key> is not an object`, exit 2, unchanged.
**Where**: `src/spinagram/mcp_server/install.py`
**Depends on**: T11
**Requirement**: INST-09

**Done when**:

- [x] Test: non-object key → ValueError, file unchanged; CLI exit 2

**Tests**: unit
**Gate**: quick
**Commit**: `fix(mcp): refuse configs whose server key is not an object`

---

### T13: Error result shape in the spec (gap 6) [x]

**What**: MCP-10 states the result: `isError: true` and one text content equal to the message, without the SDK's "Error executing tool" prefix.
**Where**: `.specs/features/mcp-server/spec.md`
**Depends on**: T12
**Requirement**: MCP-10

**Done when**:

- [x] `validate_spec.py` clean; build gate passes

**Tests**: none
**Gate**: build
**Commit**: `docs(specs): define the mcp error result`

---

### T14: Codex output must parse (gap 1, bug) [x]

**What**: The written TOML is parsed before writing; if the entry cannot be added as a table (e.g. `mcp_servers` is an inline table) → `cannot parse <file>: … edit it by hand`, exit 2, unchanged.
**Where**: `src/spinagram/mcp_server/install.py`
**Depends on**: None (Phase 2 done)
**Requirement**: INST-07, INST-09

**Done when**:

- [x] Test: inline-table `mcp_servers` → ValueError, file unchanged

**Tests**: unit
**Gate**: quick
**Commit**: `fix(mcp): refuse codex configs the new table would break`

---

### T15: Server theme reaches the tools (gap 2) [x]

**What**: A brand theme (outside the root) changes the rendered SVG colours; kills F1.
**Where**: `tests/test_mcp_tools.py`
**Depends on**: T14
**Requirement**: MCP-11

**Done when**:

- [x] Ignoring the server theme fails a test

**Tests**: unit
**Gate**: quick
**Commit**: `test(mcp): assert the server theme is the one tools use`

---

### T16: Filters that remove results (gaps 3-5) [x]

**What**: `styles(select=)` on a styled spec drops elements; previews honour `only`; `icons_search(pack=)` with two packs (kills F3, F7, F11).
**Where**: `tests/test_mcp_server.py`
**Depends on**: T15
**Requirement**: MCP-03, MCP-07, MCP-08

**Done when**:

- [x] Each mutant fails a test
- [x] Build gate passes

**Tests**: integration
**Gate**: build
**Commit**: `test(mcp): exercise the select, only and pack filters`

---

### T17: Exact select output and Codex files without a final newline (N24, N17) [x]

**What**: `styles(select="edge")` on `examples/styling/styled.py` equals `check --json --select edge` exactly and is non-empty; a Codex config without a final newline gets the entry after a newline.
**Where**: `tests/test_mcp_tools.py`
**Depends on**: None (Phase 3 done)
**Requirement**: MCP-07, INST-01

**Done when**:

- [x] N24 and N17 each fail a test
- [x] Build gate passes

**Tests**: unit
**Gate**: build
**Commit**: `test(mcp): compare select output exactly and append to unterminated codex files`

---

### T18: Sibling-prefix root, one error text, quoted force, default limit (G1, G9, G5, G20) [x]

**What**: `../root2/x.yaml` is outside a root named `root` (G1); an error result has exactly one content (G9); `--force` replaces a Codex entry whose name needs quoting (G5); `icons_search` returns 40 of 45 hits by default, via `Tools` and the server (G20).
**Where**: `tests/test_mcp_server.py`
**Depends on**: None (Phase 4 done)
**Requirement**: MCP-08, MCP-09, MCP-10, INST-08

**Done when**:

- [ ] Each of G1, G9, G5, G20 fails a test
- [ ] Build gate passes

**Tests**: integration
**Gate**: build
**Commit**: `test(mcp): pin root prefixes, single error text, quoted force and the search limit`
