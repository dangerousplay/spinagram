# Feature: MCP server for coding agents

**Status:** Draft (2026-10-19) · **Size:** Large · **Owner:** spinagram

## Problem Statement

Agents that use the `spinagram` skill drive the CLI through a shell: they parse printed paths, re-run
`check` to read issues, and open PNG files to look at results. Agents without a shell (or with shell
access gated per command) cannot use spinagram at all. An MCP server gives every MCP-capable agent typed
tools (render, check, layout, styles, icon search) and the skill text, and `spinagram mcp install` writes
the right config entry for each agent so setup is one command.

## Goals

- [ ] An agent with only the MCP server configured can render, check and look at a diagram (inline PNG
      preview) without a shell.
- [ ] `spinagram mcp install -a <agent>` produces a working config for Claude Code, Cursor, Codex, Gemini
      CLI, GitHub Copilot and opencode, project or user scope, without touching other servers in the file.

## Out of Scope

| Feature | Reason |
|---|---|
| Inline spec text in tool calls (render a YAML string, no file) | Agents write files anyway; Python specs inline would execute arbitrary code |
| `serve` UI controls over MCP (open the browser, live reload) | Separate feature; `spinagram serve` already covers it |
| Authentication / TLS on the HTTP transport | Local tool; loopback by default |
| `spinagram mcp uninstall` | Not requested; editing one entry out by hand is trivial |
| Figma upload from the server | Figma hand-off stays with the Figma MCP server (skill documents it) |
| SSE transport | Deprecated in MCP; streamable HTTP replaces it |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| Config UX | `spinagram mcp install -a AGENT [--user]` writes the agent's config; server flags are stored as `args` of the entry | User choice (2026-10-19) | y |
| Tool set | `render`, `check`, `layout`, `styles`, `icons_search` tools; skills as resources | User choice | y |
| Transport | stdio by default; `--http PORT` serves streamable HTTP | User choice | y |
| SDK | Official `mcp` package `>=2.3,<3` (`MCPServer` API), new extra `mcp`, part of `all` | Official SDK; v2 is current stable; `mcp.server.fastmcp` is gone in v2 | n |
| Launch command written to configs | `[<python of this install>, "-m", "spinagram", "mcp", …]` (new `spinagram/__main__.py`) | Works from GUI agents whose PATH lacks the venv; survives `uv tool` installs | n |
| `--uvx` install flag | Writes `uvx --from "spinagram[mcp]==<version>" spinagram mcp …` instead | For users who install nothing globally | n |
| Root confinement | `--root DIR` (default: cwd at start). Every path argument resolves under it; anything outside → tool error | An agent-facing file tool must not read/write the whole disk | n |
| Default output dir | `<root>/out` when `render` gets no `out` | Matches the CLI default `-o out` | n |
| Preview | `render` returns up to 4 PNG previews (first 4 diagrams) at 1x; needs the `png` extra; without it the result says `preview needs spinagram[png]` and still succeeds | Images are big; agents need one look, not 30 | n |
| Agent keys and files | See AGENT table below | From each tool's docs (research 2026-10-19) | n |
| Existing entry | Same server name already present → exit 1, file unchanged, unless `--force` | Same rule as `skills install` | n |
| Server name | `spinagram`, override with `--name` | Two configs (two themes) can coexist | n |
| HTTP bind | `--host 127.0.0.1` default; another host prints `warning: no authentication on <host>:<port>` to stderr and serves | User asked for HTTP for shared use; warn, don't block | n |
| `install --url URL` | Writes a remote (HTTP) entry pointing at a running `spinagram mcp --http` instead of a stdio entry | Same command for both transports | n |
| Concurrency | Tool calls that write files (`render`, `layout` with `out`) run under one lock | Two renders into one folder would interleave files | n |
| Logging | One line per tool call on stderr: `spinagram-mcp: <tool> <ms>ms ok|error` | stdout is the stdio protocol channel | n |
| Python specs | Executed as with the CLI | Same trust as `spinagram render x.py`; documented | n |
| JSONC (`opencode.jsonc`, VS Code comments) | Only plain JSON is edited; a file that fails to parse → exit 2, unchanged | Rewriting JSONC would drop comments | n |
| Codex TOML | Read with `tomllib`; the `[mcp_servers.<name>]` table is written as text (inline `env = {…}`); other text kept byte-for-byte | No TOML writer in stdlib; avoid a dependency | n |

**AGENT table** (stdio entry / HTTP entry):

| Agent | Project file | User file | Key | stdio entry | HTTP entry |
|---|---|---|---|---|---|
| claude | `.mcp.json` | `~/.claude.json` | `mcpServers` | `{"type":"stdio","command","args"}` | `{"type":"http","url"}` |
| cursor | `.cursor/mcp.json` | `~/.cursor/mcp.json` | `mcpServers` | `{"command","args"}` | `{"url"}` |
| codex | `.codex/config.toml` | `~/.codex/config.toml` | `[mcp_servers.<name>]` | `command`, `args` | `url` |
| gemini | `.gemini/settings.json` | `~/.gemini/settings.json` | `mcpServers` | `{"command","args"}` | `{"httpUrl"}` |
| copilot | `.vscode/mcp.json` | `~/.copilot/mcp-config.json` | `servers` / `mcpServers` | VS Code `{"type":"stdio",…}`, CLI `{"type":"local",…,"tools":["*"]}` | `{"type":"http","url"}` (+ `"tools":["*"]` for CLI) |
| opencode | `opencode.json` | `~/.config/opencode/opencode.json` | `mcp` | `{"type":"local","command":[cmd,…args],"enabled":true}` | `{"type":"remote","url","enabled":true}` |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Run the server and render through it ⭐ MVP

**User Story**: As a coding agent, I want MCP tools that render and check spinagram specs so that I can
produce diagrams without a shell.

**Why P1**: The core value; install is useless without it.

**Acceptance Criteria**:

1. WHEN `spinagram mcp` runs THEN the system SHALL serve MCP over stdio with the tools `render`, `check`, `layout`, `styles` and `icons_search`. <!-- MCP-01 -->
2. WHEN `render` is called with `paths` (and optional `formats`, `only`, `out`) THEN the system SHALL write the same files as `spinagram render` and return `{"written": [paths relative to root]}`. <!-- MCP-02 -->
3. WHERE the `png` extra is installed, WHEN `render` returns THEN the system SHALL attach one PNG image per diagram, at most 4, in diagram order. <!-- MCP-03 -->
4. IF the `png` extra is missing THEN `render` SHALL succeed and its result SHALL contain `"preview": "preview needs spinagram[png]"`. <!-- MCP-04 -->
5. WHEN `check` is called with `paths` THEN the system SHALL return `{"diagrams": n, "issues": [str, …]}` with the same issue strings `spinagram check` prints. <!-- MCP-05 -->
6. WHEN `layout` is called with `paths` THEN the system SHALL return the YAML text `spinagram layout` prints. <!-- MCP-06 -->
7. WHEN `styles` is called with `paths` (optional `select`) THEN the system SHALL return the same JSON as `spinagram check --json` (one report or a list). <!-- MCP-07 -->
8. WHEN `icons_search` is called with `query` (optional `pack`, `limit` default 40) THEN the system SHALL return `["pack:name", …]` as `spinagram icons search` finds them. <!-- MCP-08 -->
9. IF a path argument resolves outside the root THEN the tool SHALL return an error result `path outside root: <path>` and touch no file. <!-- MCP-09 -->
10. IF a tool raises (unknown diagram id, bad spec, missing engine) THEN the server SHALL return an error result with the message the CLI prints after `spinagram: error: ` and keep serving. <!-- MCP-10 -->
11. WHEN the server starts with `-t THEME`, `--layout ENGINE` or `--formats LIST` THEN the system SHALL use them as the defaults of every tool call that does not pass its own. <!-- MCP-11 -->
12. IF the `mcp` extra is missing THEN `spinagram mcp` SHALL print `spinagram: mcp needs the mcp extra: pip install 'spinagram[mcp]'` to stderr and exit 2. <!-- MCP-12 -->
13. The server SHALL log one line per tool call to stderr, `spinagram-mcp: <tool> <ms>ms ok` or `… error`, and write nothing else to stdout. <!-- MCP-13 -->
14. WHILE a `render` call runs the server SHALL hold later writing calls until it finishes. <!-- MCP-14 -->

**Independent Test**: In-process MCP client: list tools, call `render` on `examples/` with `formats=["svg"]`, see files on disk and paths in the result; call `check`.

---

### P1: Skills as resources ⭐ MVP

**User Story**: As an agent connected only through MCP, I want the spinagram skills so that I know how to
write good specs.

**Acceptance Criteria**:

1. WHEN a client lists resources THEN the server SHALL list `spinagram://skills/<name>` for each bundled skill with its description. <!-- MCP-15 -->
2. WHEN a client reads `spinagram://skills/<name>` THEN the server SHALL return that skill's `SKILL.md` text (`text/markdown`). <!-- MCP-16 -->

**Independent Test**: In-process client lists and reads `spinagram://skills/spinagram`.

---

### P1: Install per agent ⭐ MVP

**User Story**: As a developer, I want `spinagram mcp install -a cursor` so that my agent can use spinagram
without me hand-writing JSON.

**Acceptance Criteria**:

1. WHEN `spinagram mcp install -a AGENT` runs THEN the system SHALL add the stdio entry of the AGENT table under the server name in the project file, creating file and folders when missing, and print `installed <name> in <file>`. <!-- INST-01 -->
2. WHEN `--user` is given THEN the system SHALL write the user file of the AGENT table instead. <!-- INST-02 -->
3. WHEN `-a` is repeated THEN the system SHALL write one entry per agent. <!-- INST-03 -->
4. WHEN `-t`, `--root`, `--formats` or `--layout` is given THEN the system SHALL append them to the entry's `args` after `mcp`, `--root` as an absolute path. <!-- INST-04 -->
5. The stdio entry SHALL launch `[sys.executable, "-m", "spinagram", "mcp", …]`; WHERE `--uvx` is given it SHALL launch `uvx --from spinagram[mcp]==<version> spinagram mcp …`. <!-- INST-05 -->
6. WHEN `--url URL` is given THEN the system SHALL write the HTTP entry of the AGENT table with that URL instead of a stdio entry. <!-- INST-06 -->
7. The system SHALL keep every other key and server in the file unchanged (JSON: same parsed values; TOML: same text outside the server's table). <!-- INST-07 -->
8. IF the server name already exists in the file THEN the system SHALL exit 1 with `already installed: <name> in <file> (use --force to replace)` and leave the file unchanged; WITH `--force` it SHALL replace that entry only. <!-- INST-08 -->
9. IF the file exists and does not parse THEN the system SHALL exit 2 with `spinagram: error: cannot parse <file>: <reason>` and leave it unchanged. <!-- INST-09 -->
10. IF `-a` names an unknown agent or is missing THEN the system SHALL exit 2 listing the known agents. <!-- INST-10 -->

**Independent Test**: In a temp dir, install for every agent; parse each file and compare the entry; re-run → exit 1; `--force` → replaced; a pre-existing other server survives.

---

### P2: Streamable HTTP

**User Story**: As a developer sharing one server between tools, I want `spinagram mcp --http 8766`.

**Acceptance Criteria**:

1. WHEN `spinagram mcp --http PORT` runs THEN the system SHALL serve the same tools and resources over streamable HTTP at `http://<host>:PORT/mcp`, host `127.0.0.1` by default. <!-- HTTP-01 -->
2. IF `--host` is not a loopback address THEN the system SHALL print `warning: no authentication on <host>:<port>` to stderr and serve. <!-- HTTP-02 -->

**Independent Test**: Start on a free port, connect an MCP HTTP client, call `check`.

---

### P2: Skill documents the server

**Acceptance Criteria**:

1. The `spinagram` skill SHALL document the MCP tools, `spinagram mcp install` and the root rule in a section `## MCP server`. <!-- DOC-01 -->

---

## Edge Cases

- IF `paths` is empty or finds no diagram THEN the tool SHALL return the error `no diagrams found` (CLI message).
- IF the PNG preview fails for another reason (e.g. Chromium not installed) THEN `render` SHALL succeed with `"preview": "preview failed: <first line of the error>"`.
- WHEN `out` is relative THEN it SHALL resolve under the root; IF absolute outside the root THEN MCP-09 applies.
- WHEN a symlink inside the root points outside it THEN MCP-09 SHALL apply (resolve before checking).
- IF `~/.claude.json` is large THEN install SHALL rewrite it with the same values (indent 2), nothing else changed.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| MCP-01 | P1: Run the server | Tasks | Implementing |
| MCP-02 | P1: Run the server | Tasks | Implementing |
| MCP-03 | P1: Run the server | Tasks | Implementing |
| MCP-04 | P1: Run the server | Tasks | Implementing |
| MCP-05 | P1: Run the server | Tasks | Implementing |
| MCP-06 | P1: Run the server | Tasks | Implementing |
| MCP-07 | P1: Run the server | Tasks | Implementing |
| MCP-08 | P1: Run the server | Tasks | Implementing |
| MCP-09 | P1: Run the server | Tasks | Implementing |
| MCP-10 | P1: Run the server | Tasks | Implementing |
| MCP-11 | P1: Run the server | Tasks | Implementing |
| MCP-12 | P1: Run the server | Tasks | Implementing |
| MCP-13 | P1: Run the server | Tasks | Implementing |
| MCP-14 | P1: Run the server | Tasks | Implementing |
| MCP-15 | P1: Skills as resources | Tasks | Implementing |
| MCP-16 | P1: Skills as resources | Tasks | Implementing |
| INST-01 | P1: Install per agent | Tasks | Pending |
| INST-02 | P1: Install per agent | Tasks | Pending |
| INST-03 | P1: Install per agent | Tasks | Pending |
| INST-04 | P1: Install per agent | Tasks | Pending |
| INST-05 | P1: Install per agent | Tasks | Implementing |
| INST-06 | P1: Install per agent | Tasks | Pending |
| INST-07 | P1: Install per agent | Tasks | Pending |
| INST-08 | P1: Install per agent | Tasks | Pending |
| INST-09 | P1: Install per agent | Tasks | Pending |
| INST-10 | P1: Install per agent | Tasks | Pending |
| HTTP-01 | P2: Streamable HTTP | Tasks | Implementing |
| HTTP-02 | P2: Streamable HTTP | Tasks | Implementing |
| DOC-01 | P2: Skill docs | Tasks | Pending |

**Coverage:** 29 total, 0 mapped to tasks, 29 unmapped ⚠️

---

## Success Criteria

- [ ] An in-process MCP client renders `examples/` and gets files plus a preview.
- [ ] `spinagram mcp install` writes a parseable entry for all six agents, both scopes, and preserves other servers.
