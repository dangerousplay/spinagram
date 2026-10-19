# Validation: mcp-server

**Verdict**: FAIL
**Date**: 2026-10-19
**Iteration**: 2 of 3
**Spec**: `.specs/features/mcp-server/spec.md`
**Diff range**: `b79feec..070e0b5` (branch `feat/mcp-server`, 16 commits; fixes `d020552..070e0b5`)
**Verifier**: independent sub-agent (author != verifier)

FAIL because 4 of 33 sensor mutants survived (the server's `-t` is never shown to reach a tool; `styles` `select`, `render` previews with `only`, and `icons_search` `pack` are asserted on fixtures where the argument changes nothing), and a probe found that a valid Codex config with an inline `mcp_servers = {…}` table is rewritten into invalid TOML. All iteration-1 gaps are fixed and their mutants are now killed.

## Iteration history

| Iteration | Verdict | Findings | Outcome |
|---|---|---|---|
| 1 (`b79feec..4e22dc1`) | FAIL | server theme outside the root broke every call; M5 (default layout for `check`/`layout`) and M26 (JSON indent 2) survived; Codex `--force` dropped a comment above the next table; `{"mcpServers": []}` gave a traceback; MCP-10 result shape not in the spec | T9–T13 written and done |
| 2 (this run) | FAIL | iteration-1 items all fixed (re-run mutants killed); 4 new survivors (F1, F3, F7, F11) and 1 probe bug (Codex inline table) | gaps below |

---

## Task Completion

| Task | Status | Notes |
|---|---|---|
| T1–T8 | Done | verified in iteration 1 |
| T9 Server theme outside the root | Done | fixed (`tools.py:19`, `:29-33`); the test does not show the theme is *used* (F1) |
| T10 Layout default on every tool | Done | M5 now killed (`tests/test_mcp_tools.py:175-194`) |
| T11 JSON text and TOML comments | Done | M26 and the comment probe now killed |
| T12 Server key that is not an object | Done | JSON and TOML both refused, exit 2 |
| T13 Error result shape in the spec | Done | MCP-10 now states `isError: true`, one text content, no SDK prefix |

---

## Spec-Anchored Acceptance Criteria

| ID | Spec-defined outcome | `file:line` + assertion | Result |
|---|---|---|---|
| MCP-01 | stdio server with the five tools | `tests/test_mcp_server.py:45` sorted names `== ["check","icons_search","layout","render","styles"]`; `tests/test_mcp_cli.py:52` real stdio pipe `["diagrams"] == 1` | PASS |
| MCP-02 | same files as `spinagram render`; `{"written": [root-relative]}` | `tests/test_mcp_tools.py:43` names == CLI files; `:44` relative and exists; `:45` under `out`; `:47` bytes equal; `:52` only+out exact list; `tests/test_mcp_server.py:63` | PASS |
| MCP-03 | one PNG per diagram, ≤4, diagram order | `tests/test_mcp_server.py:65` `["image/png"]*4`; `:67` `== ["M0","M1","M2","M3"]`; `:68`; `:82` real Chromium (ran) | GAP (minor) — previews are never asserted with `only`; F7 (previews of every diagram in `paths`, ignoring `only`) survived |
| MCP-04 | succeed with `"preview": "preview needs spinagram[png]"` | `tests/test_mcp_server.py:91` `not r.is_error`; `:93` exact note | PASS |
| MCP-05 | `{"diagrams": n, "issues": [CLI strings]}` | `tests/test_mcp_tools.py:59` `== 3`; `:60` `issues == lines[:-1]` (non-empty) | PASS |
| MCP-06 | YAML text `spinagram layout` prints | `tests/test_mcp_tools.py:65` `layout_yaml(...) == cli(...)` | PASS |
| MCP-07 | same JSON as `check --json`; one report or list; optional `select` | `tests/test_mcp_tools.py:70` `== json.loads(cli … --json)`; `:73` list of 2; `:75` select == CLI `--select node` | GAP — `decision.yaml` has 0 styled elements, so `:75` compares `[] == []`; F3 (`select` ignored) survived. `examples/styling` has 11 elements, 4 match `edge` (probe) |
| MCP-08 | `["pack:name"]`, optional `pack`, `limit` default 40, as CLI | `tests/test_mcp_tools.py:90` == CLI; `:91` exact; `:92` limit 1; `:93` empty | GAP (minor) — only one pack is fetched in the test, so the `pack` filter is unobservable; F11 (filter ignored) survived |
| MCP-09 | error `path outside root: <path>`, no file touched | `tests/test_mcp_tools.py:103` `match="^path outside root: "` (4 cases); `:105`; `:161` call theme `../outside`; `tests/test_mcp_server.py:129` exact text | PASS |
| MCP-10 | `isError: true`, one text content equal to the CLI message, no SDK prefix, keeps serving | `tests/test_mcp_server.py:128` `bad.is_error and text == "no diagrams found"`; `:129`; `:130`; `:131` next call ok | PASS (R-M13 killed) |
| MCP-11 | `-t`/`--layout`/`--formats` are defaults of `render`/`check`/`layout`/`styles`; `-t` resolves against the start cwd, not root-checked | layout: `tests/test_mcp_tools.py:190` `seen == ["flex","flex"]`, `:194` overrides; formats/layout render: `:136-138`; theme outside root: `:151`, `:155` `t.theme == str(theme.resolve())`, `:156`; `tests/test_mcp_cli.py:104` | GAP — no test shows the server theme reaches a tool: `:136` asserts `root.name == "default"` (what `Theme.load(None)` also returns) and `:151`/`:156` assert only `diagrams == 1`; F1 (server theme ignored) survived |
| MCP-12 | stderr message, exit 2 | `tests/test_mcp_cli.py:36-37` | PASS |
| MCP-13 | one stderr log line per call; nothing on stdout | `tests/test_mcp_server.py:145-149` | PASS |
| MCP-14 | later writing calls wait | `tests/test_mcp_server.py:179` `peak[0] == 1` | PASS |
| MCP-15 | list `spinagram://skills/<name>` with description | `tests/test_mcp_server.py:186` | PASS |
| MCP-16 | SKILL.md text, `text/markdown` | `tests/test_mcp_server.py:189-190` | PASS |
| INST-01 | stdio entry per AGENT table; create dirs; `installed <name> in <file>` | `tests/test_mcp_install.py:70-71`; `:84`; `:170`; `tests/test_mcp_cli.py:141` | PASS — but see probe 1 (Codex inline table → invalid TOML written) |
| INST-02 | `--user` writes the user file | `tests/test_mcp_install.py:70` (user=True); `:79-81`; `:169`; `tests/test_mcp_cli.py:149` | PASS |
| INST-03 | one entry per `-a` | `tests/test_mcp_cli.py:156` | PASS |
| INST-04 | flags after `mcp`; `--root` absolute; `-t` absolute when an existing folder, built-in name as given | `tests/test_mcp_install.py:59-60`; `tests/test_mcp_tools.py:170` `== ["-t", str((tmp_path/"brand").resolve())]`; `:171` `["-t","default"]`; `tests/test_mcp_cli.py:165` | PASS (R-I4 killed) |
| INST-05 | `sys.executable -m spinagram mcp …`; `--uvx` pinned | `tests/test_mcp_install.py:50-53`; `tests/test_mcp_cli.py:13`, `:169` | PASS |
| INST-06 | HTTP entry per AGENT table | `tests/test_mcp_install.py:91`, `:99`, `:191`; `tests/test_mcp_cli.py:171` | PASS |
| INST-07 | other keys/servers unchanged (JSON values; TOML text outside the table) | `tests/test_mcp_install.py:110-111`; `:130`; `:181`; `:209`; `:237` comment above next table kept, exact text | PASS (R-G4 killed) |
| INST-08 | exit 1 + exact message, unchanged; `--force` replaces only the entry | `tests/test_mcp_install.py:120-121`, `:130`, `:201-209`; `tests/test_mcp_cli.py:180-185` | PASS |
| INST-09 | exit 2, `spinagram: error: cannot parse <file>: <reason>`, unchanged | `tests/test_mcp_cli.py:191-193`, `:208-209` (`mcpServers is not an object`); `tests/test_mcp_install.py:138-140`, `:250`, `:260`, `:217-219` | PASS (R-G5, R-G5t killed) |
| INST-10 | unknown/missing agent → exit 2 listing agents | `tests/test_mcp_cli.py:198-202` | PASS |
| HTTP-01 | streamable HTTP at `/mcp`, 127.0.0.1 default | `tests/test_mcp_cli.py:80`, `:105` | PASS |
| HTTP-02 | non-loopback warning, serve | `tests/test_mcp_cli.py:116-120` | PASS |
| DOC-01 | `## MCP server`: tools, install, root rule | `src/spinagram/agent_skills/spinagram/SKILL.md:242`, `:246-256`, `:257` (docs: build gate) | PASS |

**Status**: 25/29 ACs matched; MCP-03, MCP-07, MCP-08, MCP-11 have assertions that do not discriminate one argument each. No spec-precision gaps (the iteration-1 MCP-10 note is closed by T13).

---

## Edge Cases

| Edge case | Evidence | Result |
|---|---|---|
| empty `paths` / no diagram → `no diagrams found` | `tests/test_mcp_tools.py:118-121`; `tests/test_mcp_server.py:128` | PASS |
| other preview failure → `preview failed: <first line>` | `tests/test_mcp_server.py:103` exact text | PASS |
| relative `out` under root; absolute outside → MCP-09 | `tests/test_mcp_tools.py:51-53`; `:99` (F22 killed) | PASS |
| symlink in root pointing outside → MCP-09 | `tests/test_mcp_tools.py:112` | PASS |
| large `~/.claude.json` same values, indent 2 | `tests/test_mcp_install.py:111` values; `:226` exact indent-2 text with final newline | PASS (R-M26 killed) |

---

## Gate Check

- **Lint**: `set -o pipefail; uv run ruff check src tests examples` → `All checks passed!` (exit 0)
- **Build**: `set -o pipefail; uv run --all-extras pytest -q` → **747 passed, 3 skipped**, 0 failed (exit 0)
- **Feature tests**: 78 passed (4 files)
- **Skipped**: same 3 as iteration 1 (dot runtime ×2, soffice) — pre-existing, unrelated; the real-Chromium preview test ran.
- **Test count**: 669 before the feature → 736 at iteration 1 → 747 now (+11 fix tests); none removed or weakened.

---

## Discrimination Sensor

Scratch: `git -C mcpwt worktree add --detach …/scratchpad/verify-mcp2 HEAD`; each mutant applied by exact-string replacement in the scratch, run with `PYTHONPATH=verify-mcp2/src uv run --project mcpwt --all-extras python -m pytest -q -p no:cacheprovider` over `tests/test_mcp_{tools,server,install,cli}.py` (scratch import path confirmed, baseline 78 passed), then `git checkout -- <file>`. Scratch removed with `git worktree remove --force`; `git -C mcpwt status --porcelain` = baseline (`?? web/node_modules`) before and after.

### Re-runs (iteration-1 survivors and probe findings)

| # | File | Mutation | Result | Killed by |
|---|---|---|---|---|
| R-M5a | `tools.py:54` | `scenes` ignores the server layout | Killed | `test_layout_default_on_every_tool` |
| R-M5b | `tools.py:69` | `layout_yaml` ignores the server layout | Killed | same |
| R-M26 | `install.py:99` | JSON `indent=4` | Killed | `test_json_text_is_indented_two` |
| R-G1 | `tools.py:29-33` | iteration-1 `_theme` restored (root-checks the server theme) | Killed | `test_server_theme_outside_root` |
| R-G1b | `tools.py:19` | server theme not resolved at start | Killed | same |
| R-G4 | `install.py:133` | comment walk-back removed | Killed | `test_codex_force_keeps_the_comment_above_the_next_table` |
| R-G5 | `install.py:93-94` | non-object key check removed | Killed | `test_server_key_not_an_object[*]`, `test_install_server_key_not_an_object_exit_2` |
| R-G5t | `install.py:117-118` | TOML `mcp_servers` table check removed | Killed | `test_codex_mcp_servers_not_a_table` |
| R-I4 | `install.py:37` | `-t` folder kept relative | Killed | `test_install_makes_an_existing_theme_absolute` |
| R-M13 | `server.py:45` | error text prefixed `Error executing tool: ` | Killed | `test_errors_carry_the_cli_message…` |

### Fresh mutants (not tried in iteration 1)

| # | File | Mutation | Result | Killed by |
|---|---|---|---|---|
| F1 | `tools.py:32` | server theme ignored (`Theme.load(None)`) | **Survived** | - |
| F2 | `tools.py:33` | per-call theme not root-checked | Killed | `test_call_theme_path_stays_confined` |
| F3 | `tools.py:80` | `styles` `select` ignored | **Survived** | - |
| F4 | `tools.py:82` | `styles` always a list | Killed | `test_styles_matches_check_json` |
| F5 | `tools.py:70` | `layout` always a list | Killed | `test_layout_matches_the_cli` |
| F6 | `tools.py:59` | issues of the first diagram only | Killed | `test_check_matches_the_cli` |
| F7 | `server.py:64` | previews ignore `only` | **Survived** | - |
| F8 | `server.py:64` | previews of the last 4 | Killed | `test_render_returns_paths_and_previews_in_order` |
| F9 | `install.py:104` | TOML key never quoted | Killed | `test_codex_url_and_quoted_values` |
| F10 | `install.py:66` | opencode `enabled: false` | Killed | `test_stdio_entry_per_agent_and_scope[*-opencode]` |
| F11 | `tools.py:88` | `icons_search` `pack` filter ignored | **Survived** | - |
| F12 | `tools.py:48` | `gallery=False` | Killed | `test_render_writes_what_the_cli_writes` |
| F13 | `tools.py:59` | `diagrams` = number of paths | Killed | `test_check_matches_the_cli` |
| F14 | `install.py:70` | Copilot CLI `tools` dropped (stdio and HTTP) | Killed | `test_copilot_vscode_and_cli[True]`, `test_copilot_http[True]` |
| F15 | `cli.py` `_mcp` | `localhost` not loopback | Killed | `test_non_loopback_host_warns` |
| F16 | `install.py:98` | JSON parent folders not created | Killed | `test_stdio_entry_per_agent_and_scope[*]` |
| F17 | `tools.py:25` | root check against `root.parent` | Killed | `test_paths_outside_root_are_refused`, symlink, call theme |
| F18 | `server.py:65-66` | missing-png note removed | Killed | `test_preview_needs_the_png_extra` |
| F19 | `install.py:136` | TOML replace drops the rest of the file | Killed | `test_codex_duplicate_and_force` |
| F20 | `cli.py` `_mcp_install` | message ignores `--name` | Killed | `test_install_several_agents` |
| F21 | `install.py:119` | TOML always appends (duplicate never seen) | Killed | `test_codex_duplicate_and_force` |
| F22 | `tools.py:47` | `out` not root-checked | Killed | `test_paths_outside_root_are_refused[2]` |
| F23 | `cli.py` `_mcp` | `--formats` ignored | Killed | `test_flags_reach_the_server` |

Equivalence review of the 4 survivors: none is equivalent. F1 changes the theme of every call (`Theme.load(None).root` is the built-in default, not the `-t` folder); F3 changes the `styles` result on any spec with styled elements (`examples/styling`: 11 elements vs 4 with `select="edge"`); F7 previews diagrams that `only` excluded; F11 returns hits from every fetched pack.

**Sensor depth**: expanded (10 re-runs + 23 fresh; feature writes user config files and confines file access)
**Result**: 29/33 killed — FAIL (all 10 re-runs killed)

---

## Probes (behaviour outside the tests)

1. **Codex inline table corrupts the config.** `.codex/config.toml` = `mcp_servers = { github = { url = "x" } }` (valid TOML) → `install -a codex` appends `[mcp_servers.spinagram]` and writes a file `tomllib` rejects (`Cannot declare ('mcp_servers', 'spinagram') twice`). `install.py:117-120` only checks that `mcp_servers` is a dict, which an inline table also is. Codex then fails to read its own config. Dotted keys (`mcp_servers.github.url = …`), `[[array]]` tables and a file without a final newline all produce valid TOML.
2. Codex `--force` when our table is last and ends with a comment line → that comment is dropped. It sits inside our table, so INST-07 ("text outside the server's table") holds; acceptable.
3. `Tools(root, theme="themes/brand")` with the folder outside the root → `_theme(None).root` is the brand folder (iteration-1 bug fixed).

---

## Code Quality

| Principle | Status |
|---|---|
| Minimum code / surgical / no scope creep | OK (fixes touch only `tools.py`, `install.py`, tests, spec) |
| Matches patterns | OK |
| Spec-anchored outcome check | Gaps in MCP-03/07/08/11 (non-discriminating fixtures) |
| Per-layer coverage | tools: one optional argument each in MCP-07/08 unasserted; server/install/CLI: happy + edge + error covered |
| Every test maps to an AC / edge / Done-when | OK (fix tests tagged with T9–T12 and their IDs) |
| Documented guidelines | `pyproject.toml` (ruff, pytest), `.github/workflows/ci.yml` |

---

## Ranked Gaps / Fix Tasks

1. **Major — INST-01/INST-07: Codex config with an inline `mcp_servers = {…}` is rewritten as invalid TOML** (`src/spinagram/mcp_server/install.py:117-120`). Fix: parse the output with `tomllib` before writing; when it does not parse (or when `mcp_servers` is not declared as a `[mcp_servers…]` table), raise `cannot parse <file>: mcp_servers is an inline table; edit it by hand` (exit 2, file unchanged). Test: inline-table file → ValueError, bytes unchanged.
2. **Major — MCP-11: no test shows the server `-t` reaches a tool** (F1; `tests/test_mcp_tools.py:136`, `:151`, `:156`). Fix: with the outside-root brand theme, assert the theme a tool uses is that folder (e.g. spy `api.render`/`api.scenes` and assert `theme.root == theme_dir.resolve()`, or assert a brand token in `styles` output), for `render` and one of `check`/`layout`/`styles`.
3. **Minor — MCP-07: `select` asserted on a spec with no styled elements** (F3; `tests/test_mcp_tools.py:74-75`). Fix: run the `select` comparison on a spec with a stylesheet (e.g. copy `examples/styling` into the root) and assert the selected list is non-empty and shorter than the full list, equal to CLI `--select`.
4. **Minor — MCP-03: previews not asserted with `only`** (F7; `src/spinagram/mcp_server/server.py:64`). Fix: in `test_render_returns_paths_and_previews_in_order`, a call with `only=["M3","M1"]`-style filter asserts previews are of the selected diagrams only.
5. **Minor — MCP-08: `pack` filter unobservable** (F11; `tests/test_mcp_tools.py:78-93`). Fix: fetch a second pack containing a matching icon and assert `pack=["tiny"]` excludes it.

---

## Requirement Traceability Update

| Requirement | New status |
|---|---|
| MCP-01, 02, 04–06, 09, 10, 12–16 | Verified |
| MCP-03, MCP-07, MCP-08 | Needs test fix (gaps 3–5) |
| MCP-11 | Needs test fix (gap 2); iteration-1 defect fixed |
| INST-01 | Needs fix (gap 1, Codex inline table) |
| INST-02..10 | Verified |
| HTTP-01, HTTP-02, DOC-01 | Verified |

---

## Summary

**Overall**: Not ready (FAIL), iteration 2 of 3
**Spec-anchored check**: 25/29 ACs matched; 4 with a non-discriminating argument; 0 spec-precision gaps
**Sensor**: 29/33 killed (10/10 re-runs, 19/23 fresh)
**Gate**: ruff clean; 747 passed, 3 skipped (pre-existing), 0 failed

**What works**: every iteration-1 gap is fixed and pinned by a killing test; root confinement, error results, logging, the lock, resources, all six agent writers and both transports.

**validate_state**: `python3 …/tlc-spec-driven/scripts/validate_state.py mcp-server` → `ERROR mcp-server: validation.md verdict is FAIL - route the ranked gaps to fix tasks, then re-verify (feature is not done)` (exit 1, expected for a FAIL verdict)

**Lessons recorded**: L-044 (filter arguments need a fixture the filter changes; F3/F7/F11), L-045 (configured value distinct from the default; F1), L-046 (parse text-edited config before writing; probe 1).
