# Validation: mcp-server

**Verdict**: FAIL
**Date**: 2026-10-19
**Spec**: `.specs/features/mcp-server/spec.md`
**Diff range**: `b79feec..4e22dc1` (branch `feat/mcp-server`, 10 commits)
**Verifier**: independent sub-agent (author != verifier)

FAIL because 2 of 40 sensor mutants survived (untested behaviour: MCP-11 default layout for `check`/`layout`; the edge case "indent 2" for JSON rewrites), and a probe found a real MCP-11 defect: a server default theme outside the root breaks every tool call.

---

## Task Completion

| Task | Status | Notes |
|---|---|---|
| T1 `python -m spinagram`, `mcp` extra | Done | `pyproject.toml` `mcp = ["mcp>=2.3,<3"]`, in `all` |
| T2 Tool functions | Done | default-layout gap (M5) |
| T3 MCP binding | Done | - |
| T4 `spinagram mcp` | Done | - |
| T5 JSON writers | Done | indent gap (M26) |
| T6 Codex TOML writer | Done | comment before next table dropped on `--force` (minor) |
| T7 `spinagram mcp install` | Done | - |
| T8 Skill docs | Done | - |

---

## Spec-Anchored Acceptance Criteria

| ID | Spec-defined outcome | `file:line` + assertion | Result |
|---|---|---|---|
| MCP-01 | stdio server with tools render/check/layout/styles/icons_search | `tests/test_mcp_server.py:45` `sorted(t.name …) == ["check","icons_search","layout","render","styles"]`; `tests/test_mcp_cli.py:52` real stdio pipe `json.loads(r.content[0].text)["diagrams"] == 1` | PASS |
| MCP-02 | same files as `spinagram render`; `{"written": [root-relative]}` | `tests/test_mcp_tools.py:43` names == CLI files; `:44` not absolute and file exists; `:47` bytes equal CLI; `:52` `== ["build/diagrams/EX2-….svg"]` (only+out); `tests/test_mcp_server.py:63` | PASS |
| MCP-03 | one PNG per diagram, at most 4, diagram order | `tests/test_mcp_server.py:65` mime `["image/png"]*4`; `:67` `== ["M0","M1","M2","M3"]`; `:68` fifth never rendered; `:82` real Chromium (ran, not skipped) | PASS |
| MCP-04 | succeed with `"preview": "preview needs spinagram[png]"` | `tests/test_mcp_server.py:91` `not r.is_error`; `:93` `body["preview"] == "preview needs spinagram[png]" and body["written"]` | PASS |
| MCP-05 | `{"diagrams": n, "issues": [CLI strings]}` | `tests/test_mcp_tools.py:59` `== 3`; `:60` `res["issues"] == lines[:-1]` (non-empty) | PASS (note: CLI `info: unused selector` lines are not issues and are excluded; fixture has none) |
| MCP-06 | YAML text `spinagram layout` prints | `tests/test_mcp_tools.py:65` `layout_yaml(...) == cli(... "layout" ...)` | PASS |
| MCP-07 | same JSON as `check --json`, one report or list; `select` | `tests/test_mcp_tools.py:70` `== json.loads(cli … --json)`; `:73` list of 2; `:75` select == CLI `--select` | PASS |
| MCP-08 | `["pack:name"]`, limit default 40, as CLI | `tests/test_mcp_tools.py:90` == CLI split; `:91` `== ["tiny:dot","tiny:dot-big"]`; `:92` limit=1 | PASS (default 40 not exercised; signature `tools.py:82`) |
| MCP-09 | error `path outside root: <path>`, no file touched | `tests/test_mcp_tools.py:103` `match="^path outside root: "` for `..`, `/etc`, absolute `out`, `specs/../../`; `:105` `not (root/"out").exists()`; `tests/test_mcp_server.py:129` `== "path outside root: ../x.yaml"` | PASS |
| MCP-10 | error result with the CLI message, keeps serving | `tests/test_mcp_server.py:128` `bad.is_error and text == "no diagrams found"`; `:130` `startswith("invalid selector '::'")`; `:131` next call ok | PASS — see spec-precision note 1 |
| MCP-11 | `-t`/`--layout`/`--formats` are defaults of every call that does not pass its own | `tests/test_mcp_tools.py:136` render theme/formats/layout defaults; `:138` overrides; `tests/test_mcp_cli.py:104` flags reach `Tools` | GAP — default layout only asserted for `render` (M5 survived); server theme outside root breaks every call (probe, Gap 1) |
| MCP-12 | stderr `spinagram: mcp needs the mcp extra: pip install 'spinagram[mcp]'`, exit 2 | `tests/test_mcp_cli.py:36` `main(["mcp"]) == 2`; `:37` exact stderr | PASS |
| MCP-13 | one stderr line `spinagram-mcp: <tool> <ms>ms ok|error`, nothing on stdout | `tests/test_mcp_server.py:145` 2 lines; `:147`/`:148` `re.fullmatch(... ok/error)`; `:149` `out == ""` | PASS |
| MCP-14 | later writing calls wait for a running render | `tests/test_mcp_server.py:179` `peak[0] == 1` over 3 concurrent clients | PASS (M9 killed) |
| MCP-15 | list `spinagram://skills/<name>` with description | `tests/test_mcp_server.py:186` uri→description map equals `skills.available()` | PASS |
| MCP-16 | read returns SKILL.md text, `text/markdown` | `tests/test_mcp_server.py:189` mime; `:190` text equals file | PASS |
| INST-01 | stdio entry per AGENT table in project file, create dirs, print `installed <name> in <file>` | `tests/test_mcp_install.py:70-71` path + exact `{key: {"spinagram": STDIO[agent]}}`; `:84` copilot VS Code; `:170` codex; `tests/test_mcp_cli.py:141` exact stdout | PASS |
| INST-02 | `--user` writes the user file | `tests/test_mcp_install.py:70` `path == home/usr` (parametrized user=True); `:79-81` Copilot CLI; `:169`; `tests/test_mcp_cli.py:149` | PASS |
| INST-03 | one entry per `-a` | `tests/test_mcp_cli.py:156` two exact `installed diagrams in …` lines | PASS |
| INST-04 | flags appended after `mcp`, `--root` absolute | `tests/test_mcp_install.py:59-60` exact list; `tests/test_mcp_cli.py:165` exact args | PASS |
| INST-05 | `[sys.executable,"-m","spinagram","mcp",…]`; `--uvx` → `uvx --from spinagram[mcp]==<v> spinagram mcp …` | `tests/test_mcp_install.py:50-53`; `tests/test_mcp_cli.py:13` `python -m spinagram -V`; `:169` | PASS |
| INST-06 | HTTP entry of the AGENT table | `tests/test_mcp_install.py:91` `== HTTP[agent]`; `:99` copilot both scopes (+tools for CLI); `:191` codex url; `tests/test_mcp_cli.py:171` | PASS |
| INST-07 | other keys/servers unchanged (JSON values; TOML text outside the table) | `tests/test_mcp_install.py:110-111` `got == other`; `:130`; `:181` `text.startswith(CODEX_OTHER)`; `:209` | PASS (minor: on `--force` a comment line directly above the next TOML table is dropped, Gap 4) |
| INST-08 | exit 1, `already installed: <name> in <file> (use --force to replace)`, unchanged; `--force` replaces only entry | `tests/test_mcp_install.py:120` exact message; `:121` bytes unchanged; `:130`; `:201-209` codex; `tests/test_mcp_cli.py:180-185` exit 1 + stderr | PASS (stderr carries the project's `spinagram: ` prefix, same as `skills install`) |
| INST-09 | exit 2, `spinagram: error: cannot parse <file>: <reason>`, unchanged | `tests/test_mcp_cli.py:191-193`; `tests/test_mcp_install.py:138-140` (bad JSON, JSONC, array); `:217-219` TOML | PASS |
| INST-10 | unknown/missing agent → exit 2 listing known agents | `tests/test_mcp_cli.py:198-202` exact messages, nothing written | PASS |
| HTTP-01 | streamable HTTP at `http://<host>:PORT/mcp`, default 127.0.0.1 | `tests/test_mcp_cli.py:80` real HTTP client `== {"diagrams":1,"issues":[]}`; `:105` default host | PASS (resources over HTTP not exercised) |
| HTTP-02 | non-loopback → `warning: no authentication on <host>:<port>`, serve | `tests/test_mcp_cli.py:116-120` exact warning; none for 127.0.0.1/localhost/::1 | PASS |
| DOC-01 | `## MCP server` section: tools, install, root rule | `src/spinagram/agent_skills/spinagram/SKILL.md:242` section; tools `:256`, root `:257`, install `:246-253` (docs: build gate only, per matrix) | PASS |

**Status**: 28/29 ACs matched; MCP-11 partially covered and defective.

### Spec-precision notes

1. MCP-10 / MCP-09 "error result" — the spec does not define the MCP shape. Implementation returns `CallToolResult(is_error=True, content=[TextContent(text=<message>)])` itself (`src/spinagram/mcp_server/server.py:45`) to avoid the SDK `ToolError` prefix `Error executing tool …`; tests pin `is_error` and the exact text. Defined de facto by the tests; spec should state "`isError: true`, single text content equal to the message, no SDK prefix".
2. MCP-10 `KeyError` messages: `str(KeyError(...))` keeps quotes (`'…'`); the CLI prints the same `{exc}`, so it matches, but no test covers a KeyError path.

---

## Edge Cases

| Edge case | Evidence | Result |
|---|---|---|
| empty `paths` / no diagram → `no diagrams found` | `tests/test_mcp_tools.py:118-121`; `tests/test_mcp_server.py:128` | PASS |
| other preview failure → `preview failed: <first line>` | `tests/test_mcp_server.py:103` exact text | PASS |
| relative `out` under root; absolute outside → MCP-09 | `tests/test_mcp_tools.py:51-53`; `:99` | PASS |
| symlink in root pointing outside → MCP-09 | `tests/test_mcp_tools.py:112` `match="^path outside root: link/x.yaml$"` | PASS |
| large `~/.claude.json` rewritten with same values, indent 2 | `tests/test_mcp_install.py:111` values only | GAP — indent 2 not asserted (M26 survived) |

---

## Gate Check

- **Lint**: `set -o pipefail; uv run ruff check src tests examples` → `All checks passed!` (exit 0)
- **Build**: `uv run --all-extras pytest -q` → **736 passed, 3 skipped**, 0 failed (exit 0)
- **Quick (feature)**: 67 passed
- **Skipped**: `tests/test_autolayout.py:155`, `:165` (dot runtime not installed), `tests/test_pptx_svg.py:129` (soffice not installed) — pre-existing, unrelated. `test_preview_with_the_real_png_backend` ran (Chromium present).
- **Test count**: 669 before → 736 after (+67, all in the four new files); no test removed.

---

## Discrimination Sensor

Scratch: `git worktree add --detach …/scratchpad/verify-mcp HEAD`; each mutant applied there, run with `PYTHONPATH=verify-mcp/src uv run --project mcpwt --all-extras python -m pytest -q -x -p no:cacheprovider` over the 4 feature test files, restored with `git checkout`. Worktree removed; `git -C mcpwt status --porcelain` = baseline (`?? web/node_modules`) before and after.

| # | File | Mutation | Result | Killed by |
|---|---|---|---|---|
| M1 | `tools.py:23` | root check disabled | Killed | `test_paths_outside_root_are_refused` |
| M2 | `tools.py:22` | `normpath` instead of `resolve` (symlinks not followed) | Killed | `test_symlink_out_of_root_is_refused` |
| M3 | `tools.py:46` | server default formats ignored | Killed | `test_server_defaults_and_call_overrides` |
| M4 | `tools.py:47` | per-call layout loses to server default | Killed | same |
| M5 | `tools.py:52` | `check`/`scenes` ignore server default layout | **Survived** | - |
| M6 | `tools.py:45` | default out `build` | Killed | `test_render_writes_what_the_cli_writes` |
| M7 | `tools.py:87` | limit off by one | Killed | `test_icons_search_matches_the_cli` |
| M8 | `tools.py:48` | absolute written paths | Killed | `test_render_writes_what_the_cli_writes` |
| M9 | `server.py:60` | write lock removed | Killed | `test_renders_do_not_overlap` |
| M10 | `server.py:18` | preview cap 5 | Killed | `test_render_returns_paths_and_previews_in_order` |
| M11 | `server.py:66` | missing-png note text | Killed | `test_preview_needs_the_png_extra` |
| M12 | `server.py:68` | preview failure uses last line | Killed | `test_preview_failure_is_a_note` |
| M13 | `server.py:45` | error text prefixed `Error: ` | Killed | `test_errors_carry_the_cli_message…` |
| M14 | `server.py:45` | `is_error=False` | Killed | same |
| M15 | `server.py:47` | log line to stdout | Killed | `test_one_log_line_per_call_on_stderr` |
| M16 | `server.py:39` | log state always `ok` | Killed | same |
| M17 | `server.py:95` | resource mime `text/plain` | Killed | `test_skills_are_resources` |
| M18 | `install.py:68` | claude stdio `type` dropped | Killed | `test_stdio_entry_per_agent_and_scope` |
| M19 | `install.py:68` | Copilot CLI type `stdio` | Killed | `test_copilot_vscode_and_cli[True]` |
| M20 | `install.py:70` | Copilot CLI `tools` dropped | Killed | same |
| M21 | `install.py:55` | Copilot CLI key `servers` | Killed | same |
| M22 | `install.py:62` | gemini HTTP `url` not `httpUrl` | Killed | `test_http_entry_per_agent[gemini]` |
| M23 | `install.py:92` | JSON duplicate check removed | Killed | `test_duplicate_is_refused_unchanged` |
| M24 | `install.py:92` | `--force` ignored | Killed | `test_force_replaces_only_the_entry` |
| M25 | `install.py:91` | other servers dropped | Killed | `test_name_and_other_servers_survive` |
| M26 | `install.py:96` | JSON `indent=4` | **Survived** | - |
| M27 | `install.py:87` | non-object JSON accepted | Killed | `test_unparseable_file_is_left_alone[[]]` |
| M28 | `install.py:125` | TOML replace keeps `.env` subtable | Killed | `test_codex_duplicate_and_force` |
| M29 | `install.py:116` | TOML duplicate check removed | Killed | same |
| M30 | `install.py:128` | TOML replace drops following text | Killed | same |
| M31 | `install.py:30` | uvx unpinned | Killed | `test_launch_command` |
| M32 | `install.py:39` | `--root` not absolute | Killed | `test_server_args` |
| M33 | `install.py:18` | wrong claude user file | Killed | `test_stdio_entry_per_agent_and_scope[True-claude]` |
| M34 | `cli.py` `_mcp_install` | duplicate exit 2 | Killed | `test_install_duplicate_exit_1` |
| M35 | `cli.py` `_mcp` | loopback check inverted | Killed | `test_non_loopback_host_warns` |
| M36 | `cli.py` `_mcp_install` | agents not validated before writing | Killed | `test_install_unknown_or_missing_agent_exit_2` |
| M37 | `cli.py` `_mcp` | missing-extra exit 1 | Killed | `test_missing_extra_message` |
| M38 | `cli.py` `--host` | default `0.0.0.0` | Killed | `test_flags_reach_the_server` |
| M39 | `cli.py` `_mcp` | `--http` served over stdio | Killed | `test_http_server_answers` |
| M40 | `cli.py` `_mcp_install` | `--url` ignored | Killed | `test_install_flags_become_args` |

**Sensor depth**: expanded (40 manual mutants; feature writes user config files and confines file access)
**Result**: 38/40 killed — FAIL

---

## Probes (behaviour outside the tests)

- `Tools(root, theme="<abs dir outside root>").check([...])` → `ValueError: path outside root: <theme dir>` (`tools.py:29-30`: `self.root / ref` of an absolute `ref` is `ref`, it exists, so `self.path` refuses it). A server started with `-t /path/to/brand --root specs` fails every call; a relative `-t` is resolved against the server's cwd, which agents choose. The skill's own example `--root specs -t <theme-dir>` (`SKILL.md:249`) hits this whenever the theme is not inside `specs`.
- Codex `--force` on `[mcp_servers.spinagram]\n…\n\n# --- my profiles (keep) ---\n[profiles.fast]` → comment line removed (`install.py:125` scans to the next `[`, then joins with `"\n"`).
- `{"mcpServers": []}` → uncaught `TypeError` (traceback; not in `cli.main`'s except list).
- `[mcp_servers]\nspinagram = {…}` with `--force` → refused with `cannot parse …: … edit it by hand` (exit 2; acceptable, conservative).

---

## Code Quality

| Principle | Status |
|---|---|
| Minimum code / surgical / no scope creep | OK (only feature files, `cli.py` wiring, `pyproject.toml`, `uv.lock`, SKILL.md) |
| Matches patterns | OK (`main` error mapping, `skills install` message style) |
| Spec-anchored outcome check | OK except MCP-11 and edge case 5 |
| Per-layer coverage expectation | tools: 1:1 except MCP-11 non-render defaults; server/install/CLI: happy + edge + error covered |
| Every test maps to an AC / edge / Done-when | OK (each test tagged with its ID) |
| Documented guidelines | `pyproject.toml` (ruff, pytest), `.github/workflows/ci.yml` |

---

## Ranked Gaps / Fix Tasks

1. **Major — MCP-11: server default theme outside the root breaks every call** (`src/spinagram/mcp_server/tools.py:27-31`). Fix: resolve the server's own `-t` once at startup (relative to the launch cwd, or make `install` store `-t` as an absolute path like `--root`), and apply root confinement only to theme paths that arrive as tool arguments. Verify: test `Tools(root, theme=<dir outside root>).check(...)` succeeds and uses that theme; `server_args(theme="brand")` absolute when `brand` is a directory.
2. **Major — MCP-11 default layout not asserted for `check`/`layout`** (M5 survived; `tools.py:52`, `:67`). Fix task: in `test_server_defaults_and_call_overrides`, assert `check` and `layout_yaml` pass the server `layout` (monkeypatch `api.scenes` / `apply_layout`) and that a per-call value wins.
3. **Minor — edge case "indent 2" not asserted** (M26 survived; `install.py:96`). Fix task: assert `path.read_text() == json.dumps(expected, indent=2, ensure_ascii=False) + "\n"` in `test_name_and_other_servers_survive`.
4. **Minor — INST-07 TOML `--force` drops a comment directly above the next table** (`install.py:124-128`). Fix: stop the replaced block at the last non-comment, non-blank line before the next header, keep the trailing comments/blank lines; add a test.
5. **Minor — `mcpServers` present but not an object → traceback** (`install.py:91`). Fix: treat as `cannot parse <file>: <key> is not an object` (exit 2, unchanged).
6. **Spec-precision** — MCP-10 error-result shape (note 1) should be written into the spec.

---

## Requirement Traceability Update

| Requirement | New status |
|---|---|
| MCP-01..10, MCP-12..16 | Verified |
| MCP-11 | Needs fix (gaps 1, 2) |
| INST-01..06, INST-08..10 | Verified |
| INST-07 | Verified (minor gap 4) |
| HTTP-01, HTTP-02, DOC-01 | Verified |

---

## Summary

**Overall**: Not ready (FAIL)
**Spec-anchored check**: 28/29 ACs matched; 1 AC with gaps (MCP-11); 1 edge case uncovered; 1 spec-precision note
**Sensor**: 38/40 killed
**Gate**: ruff clean; 736 passed, 3 skipped (pre-existing), 0 failed

**validate_state**: `python3 …/tlc-spec-driven/scripts/validate_state.py mcp-server` → `ERROR mcp-server: validation.md verdict is FAIL - route the ranked gaps to fix tasks, then re-verify (feature is not done)` (exit 1, expected for a FAIL verdict)
