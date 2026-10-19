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

---

## Task Breakdown

### T1: `python -m spinagram` and the `mcp` extra [x]

**What**: `spinagram/__main__.py` runs `cli.main`; `pyproject.toml` gains `mcp = ["mcp>=2.3,<3"]`, added to `all`; `uv.lock` updated.
**Where**: `src/spinagram/__main__.py`
**Depends on**: None
**Requirement**: INST-05 (launch command)

**Done when**:

- [ ] Test: `[sys.executable, "-m", "spinagram", "-V"]` prints the version, exit 0
- [ ] Build gate passes

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

- [ ] Tests: each tool's output equals what the CLI prints for the same input; out-of-root paths, `..`, absolute `out` and symlinks → `path outside root`; relative `out` under root; empty paths → `no diagrams found`; server defaults vs per-call overrides

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

- [ ] Integration tests via `mcp.Client(server)`: tool names; render result + images (stubbed renderer: 5 diagrams → 4 images in order); missing png → note; error result text; log lines; resources list/read; concurrent renders serialised

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

- [ ] Tests: missing `mcp` import → stderr message, exit 2; `--http` on a free port answers `check` through an HTTP `mcp.Client`; `--host 0.0.0.0` prints the warning

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

- [ ] Tests per agent × scope: file path, key, exact entry (stdio, `--uvx`, `--url`); other servers and keys survive; duplicate → `FileExistsError` and unchanged bytes; force replaces only the entry; bad JSON → error, unchanged

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

- [ ] Tests: new file; existing file with other tables (text outside the table unchanged); duplicate; force; `url` entry; invalid TOML → error, unchanged

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

- [ ] Tests: `installed <name> in <file>` per agent; two `-a` → two files; flags appear in args with absolute root; duplicate → exit 1 + message; bad file → exit 2 + message; unknown/missing agent → exit 2 listing agents

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

- [ ] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `docs(skills): document the spinagram mcp server`
