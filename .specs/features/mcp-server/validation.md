# Validation: mcp-server

**Verdict**: FAIL
**Date**: 2026-10-19
**Iteration**: 3 of 3 (limit reached; escalate to the user)
**Spec**: `.specs/features/mcp-server/spec.md`
**Diff range**: `b79feec..320d0e6` (branch `feat/mcp-server`, 20 commits; iteration-3 fixes `652f75d..320d0e6`)
**Verifier**: independent sub-agent (author != verifier)

FAIL on test strength only, not behaviour. Every iteration-2 gap is fixed and its mutant is now killed (F1, F3, F7, F11 and the Codex inline-table probe). Two new mutants in spec-stated rules survived: N17 (a Codex config without a final newline is refused instead of getting the entry; INST-01) and N24 (`styles` with `select` keeps only the first match; MCP-07). HEAD behaves correctly in both cases (probed). Each is a one-assertion test fix.

## Iteration history

| Iteration | Verdict | Findings | Outcome |
|---|---|---|---|
| 1 (`b79feec..4e22dc1`) | FAIL | server theme outside the root broke every call; M5 (layout default for `check`/`layout`) and M26 (JSON indent 2) survived; Codex `--force` dropped a comment above the next table; `{"mcpServers": []}` gave a traceback; MCP-10 result shape not in the spec | T9–T13 done |
| 2 (`..070e0b5`) | FAIL | iteration-1 items fixed; F1 (server `-t` never shown reaching a tool), F3 (`select`), F7 (previews ignore `only`), F11 (`pack`) survived; probe: inline `mcp_servers = {…}` written as invalid TOML | T14–T16 done |
| 3 (this run) | FAIL | all iteration-2 items killed; 2 new spec-level survivors (N17, N24), 1 out-of-spec survivor (N20) | gaps below |

---

## Task Completion

| Task | Status | Notes |
|---|---|---|
| T1–T13 | Done | verified in iterations 1–2 |
| T14 Codex output must parse | Done | `install.py:82-91` parses the edited text and checks the entry landed; P1 killed by `tests/test_mcp_install.py:264-272` |
| T15 Server theme reaches the tools | Done | F1 killed by `tests/test_mcp_tools.py:206` |
| T16 Filters that remove results | Done | F3, F7, F11 killed (`tests/test_mcp_server.py:200-201`, `:210`, `:226-227`) |

Bookkeeping: the T14–T16 headers are `[x]` but their "Done when" checkboxes in `tasks.md` are still `[ ]`. The criteria are met.

---

## Spec-Anchored Acceptance Criteria

| ID | Spec-defined outcome | `file:line` + assertion | Result |
|---|---|---|---|
| MCP-01 | stdio server with the five tools | `tests/test_mcp_server.py:45` sorted names; `tests/test_mcp_cli.py:52` real stdio `["diagrams"] == 1` | PASS |
| MCP-02 | same files as `spinagram render`; root-relative `written` | `tests/test_mcp_tools.py:43-47`, `:52`; N1, N2 killed | PASS |
| MCP-03 | one PNG per diagram, ≤4, diagram order | `tests/test_mcp_server.py:65`, `:67`; `:210` `seen == ["M2"]` with `only` (F7 killed); N3 killed | PASS |
| MCP-04 | succeed with the `spinagram[png]` note | `tests/test_mcp_server.py:91`, `:93` | PASS |
| MCP-05 | `{"diagrams": n, "issues": [CLI strings]}` | `tests/test_mcp_tools.py:59-60` | PASS |
| MCP-06 | YAML text `spinagram layout` prints | `tests/test_mcp_tools.py:65` | PASS |
| MCP-07 | same JSON as `check --json`; optional `select` | `tests/test_mcp_tools.py:70`, `:73`; `:75` `== CLI --select node` (decision.yaml, 0 styled elements); `tests/test_mcp_server.py:200` `edges and len(edges) < len(full)`, `:201` types `== {"edge"}` | GAP (minor): the styled-spec test checks that results are a subset, not that they equal the CLI's `--select edge` output; N24 (first match only) survived |
| MCP-08 | `["pack:name"]`, `pack`, `limit` 40, as CLI | `tests/test_mcp_tools.py:90-93`; `tests/test_mcp_server.py:226-227` (F11 killed); N16 killed | PASS |
| MCP-09 | `path outside root: <path>`, no file touched | `tests/test_mcp_tools.py:103`, `:105`, `:112`, `:161`; `tests/test_mcp_server.py:129` | PASS |
| MCP-10 | `isError`, one text = CLI message, keeps serving | `tests/test_mcp_server.py:128-131`; N21 killed | PASS |
| MCP-11 | `-t`/`--layout`/`--formats` are tool defaults; `-t` not root-checked | `tests/test_mcp_tools.py:136`, `:155`, `:190`, `:194`; `:206` brand colour `#123456` in the SVG with `-t`, absent without it (F1 killed); `tests/test_mcp_cli.py:104` | PASS |
| MCP-12 | missing extra: message, exit 2 | `tests/test_mcp_cli.py:36-37` | PASS |
| MCP-13 | one stderr line per call, clean stdout | `tests/test_mcp_server.py:145-149`; N5 killed | PASS |
| MCP-14 | later writing calls wait | `tests/test_mcp_server.py:179` `peak[0] == 1`; N6 killed | PASS |
| MCP-15 | resources listed with descriptions | `tests/test_mcp_server.py:186`; N8 killed | PASS |
| MCP-16 | SKILL.md text, `text/markdown` | `tests/test_mcp_server.py:189-190`; N7 killed | PASS |
| INST-01 | stdio entry, create dirs, `installed <name> in <file>` | `tests/test_mcp_install.py:70-71`, `:84`, `:170`; `tests/test_mcp_cli.py:141`; inline table refused `tests/test_mcp_install.py:270-272` | GAP (minor): no test appends to a Codex file without a final newline. N17 (separator newlines dropped) survived: such a file is now refused with exit 2 and gets no entry. HEAD is correct (probe) |
| INST-02 | `--user` file | `tests/test_mcp_install.py:70`, `:79-81`; N12, N13 killed | PASS |
| INST-03 | one entry per `-a` | `tests/test_mcp_cli.py:156` | PASS |
| INST-04 | flags after `mcp`, absolute `--root`/theme folder | `tests/test_mcp_install.py:59-60`; `tests/test_mcp_tools.py:170-171`; N11 killed | PASS |
| INST-05 | `sys.executable -m spinagram mcp`; `--uvx` pinned | `tests/test_mcp_install.py:50-53`; N9 killed | PASS |
| INST-06 | HTTP entry per AGENT table | `tests/test_mcp_install.py:91`, `:99`; N10 killed | PASS |
| INST-07 | other keys/servers/text kept | `tests/test_mcp_install.py:110-111`, `:130`, `:209`, `:237`; `:272` inline-table file bytes unchanged | PASS |
| INST-08 | exit 1 + message; `--force` replaces only it | `tests/test_mcp_install.py:120-121`, `:201-209`; `tests/test_mcp_cli.py:180-185`; N18, N23 killed | PASS |
| INST-09 | exit 2 `cannot parse <file>: <reason>`, unchanged | `tests/test_mcp_cli.py:191-193`, `:208-209`; `tests/test_mcp_install.py:138-140`, `:250`, `:270-272`; P1, N25 killed | PASS |
| INST-10 | unknown/missing agent → exit 2 listing agents | `tests/test_mcp_cli.py:198-202`; N14 killed | PASS |
| HTTP-01 | streamable HTTP `/mcp`, 127.0.0.1 | `tests/test_mcp_cli.py:80`, `:105` | PASS |
| HTTP-02 | non-loopback warning on stderr | `tests/test_mcp_cli.py:116-120`; N15 killed | PASS |
| DOC-01 | `## MCP server` section | `src/spinagram/agent_skills/spinagram/SKILL.md:242`, `:246-257` | PASS |

**Status**: 27/29 ACs matched. MCP-07 and INST-01 each have one non-discriminating case. 0 spec-precision gaps.

---

## Edge Cases

| Edge case | Evidence | Result |
|---|---|---|
| empty / no diagram → `no diagrams found` | `tests/test_mcp_tools.py:118-121`; `tests/test_mcp_server.py:128` | PASS |
| other preview failure → `preview failed: <first line>` | `tests/test_mcp_server.py:103`; N4 killed | PASS |
| relative `out` under root; absolute outside → MCP-09 | `tests/test_mcp_tools.py:51-53`, `:99` | PASS |
| symlink pointing outside → MCP-09 | `tests/test_mcp_tools.py:112` | PASS |
| large `~/.claude.json`: same values, indent 2 | `tests/test_mcp_install.py:111`, `:226`; R-M26 killed | PASS |

---

## Gate Check

- **Lint**: `set -o pipefail; uv run ruff check src tests examples` → `All checks passed!` (exit 0)
- **Build**: `set -o pipefail; uv run --all-extras pytest -q` → **752 passed, 3 skipped**, 0 failed (exit 0)
- **Feature tests**: 83 passed (4 files)
- **Skipped**: the same 3 pre-existing skips (dot runtime ×2, soffice)
- **Test count**: 747 → 752 (+5 fix tests); none removed or weakened

---

## Discrimination Sensor

Scratch: `git -C mcpwt worktree add --detach …/scratchpad/verify-mcp3 HEAD`. Each mutant was an exact-string replacement in the scratch, run with `PYTHONPATH=verify-mcp3/src uv run --project mcpwt --all-extras python -m pytest -q -p no:cacheprovider` over `tests/test_mcp_{tools,server,install,cli}.py`, then reverted with `git checkout`. The scratch import path was confirmed (`spinagram.__file__` under `verify-mcp3/src`) and the baseline was 83 passed. The scratch was removed with `git worktree remove --force`. `git -C mcpwt status --porcelain` matched the baseline (`?? web/node_modules`) before and after.

### Re-runs (iteration-2 survivors, the probe bug, spot checks)

| # | Mutation | Result | Killed by |
|---|---|---|---|
| F1 | server theme ignored (`Theme.load(None)`) | Killed | `test_server_theme_is_the_one_tools_use` |
| F3 | `styles` `select` ignored | Killed | `test_styles_select_filters`, `test_errors_carry_the_cli_message…` |
| F7 | previews ignore `only` | Killed | `test_previews_follow_only` |
| F11 | `icons_search` `pack` ignored | Killed | `test_icons_search_pack_filter` |
| P1 | T14 parse-after-edit check disabled (inline-table bug back) | Killed | `test_codex_inline_mcp_servers_left_alone` |
| R-M5a | `scenes` ignores the server layout | Killed | `test_layout_default_on_every_tool` |
| R-M26 | JSON `indent=4` | Killed | `test_json_text_is_indented_two` |
| R-G1 | server theme root-checked (iteration-1 bug) | Killed | `test_server_defaults_and_call_overrides` |

### Fresh mutants (not tried in iterations 1–2)

| # | File | Mutation (rule) | Result | Killed by |
|---|---|---|---|---|
| N1 | `tools.py:38` | `only` ignored (MCP-02) | Killed | `test_render_only_and_relative_out` |
| N2 | `tools.py:50` | `written` absolute (MCP-02) | Killed | `test_render_writes_what_the_cli_writes` |
| N3 | `server.py:18` | 5 previews (MCP-03) | Killed | `test_render_returns_paths_and_previews_in_order` |
| N4 | `server.py:68` | last error line, not first (edge) | Killed | `test_preview_failure_is_a_note` |
| N5 | `server.py:39` | log always `ok` (MCP-13) | Killed | `test_one_log_line_per_call_on_stderr` |
| N6 | `server.py:60` | write lock removed (MCP-14) | Killed | `test_renders_do_not_overlap` |
| N7 | `server.py:95` | resource `text/plain` (MCP-16) | Killed | `test_skills_are_resources` |
| N8 | `server.py:94` | resource description dropped (MCP-15) | Killed | `test_skills_are_resources` |
| N9 | `install.py:30` | `--uvx` unpinned (INST-05) | Killed | `test_launch_command` |
| N10 | `install.py:62` | gemini HTTP `url` not `httpUrl` (INST-06) | Killed | `test_http_entry_per_agent[gemini]` |
| N11 | `install.py:39` | `--root` kept relative (INST-04) | Killed | `test_server_args` |
| N12 | `install.py:55` | Copilot CLI key `servers` (AGENT table) | Killed | `test_copilot_vscode_and_cli[True]` |
| N13 | `install.py:18` | claude user file wrong (INST-02) | Killed | `test_stdio_entry_per_agent_and_scope[True-claude]` |
| N14 | `cli.py:402` | missing `-a` lists no agents (INST-10) | Killed | `test_install_unknown_or_missing_agent_exit_2` |
| N15 | `cli.py:392` | warning on stdout (HTTP-02) | Killed | `test_non_loopback_host_warns` |
| N16 | `tools.py:89` | `limit` ignored (MCP-08) | Killed | `test_icons_search_matches_the_cli` |
| N17 | `install.py:130` | append `text + table` with no separator newlines (INST-01) | **Survived** | - |
| N18 | `cli.py:410` | `--force` not passed on (INST-08) | Killed | `test_install_duplicate_exit_1` |
| N19 | `tools.py:19` | built-in server theme name made a path (MCP-11) | Killed | `test_server_defaults_and_call_overrides` |
| N20 | `tools.py:33` | per-call theme always a root path | **Survived** | - |
| N21 | `server.py:45` | `is_error=False` (MCP-10) | Killed | `test_errors_carry_the_cli_message…` |
| N22 | `install.py:66` | opencode command drops the executable (AGENT table) | Killed | `test_stdio_entry_per_agent_and_scope[False-opencode]` |
| N23 | `install.py:143` | comment walk-back disabled (INST-07) | Killed | `test_codex_force_keeps_the_comment_above_the_next_table` |
| N24 | `tools.py:80` | `select` keeps the first match only (MCP-07) | **Survived** | - |
| N25 | `install.py:85` | T14 check accepts any parsable output | Killed | `test_codex_inline_mcp_servers_left_alone` |

### Survivor classification

- **N17: gap (INST-01).** Probe: `.codex/config.toml` = `model = "o3"` with no final newline. HEAD writes `model = "o3"\n\n[mcp_servers.spinagram]…`, which is valid. Under the mutant the T14 safety net catches the broken text and install exits 2 with `cannot add [mcp_servers.spinagram] (Expected newline …)`. The file is not corrupted, but the entry INST-01 requires is never added, and no test notices.
- **N24: gap (MCP-07).** "The same JSON as `spinagram check --json`" with `select` is compared to the CLI only on `decision.yaml`, which has no styled elements. The styled-spec test (`tests/test_mcp_server.py:200-201`) accepts any non-empty, smaller set of edges.
- **N20: out of spec, not a gap.** The per-call `theme` argument exists only on the Python `Tools` class. The MCP tools in `server.py:58-91` expose no `theme` parameter, so no MCP client can reach this path. MCP-11 only covers the server `-t` default (N19 and F1 are killed). The mutant does break a built-in per-call name (probe: `Tools(root)._theme("default")` raises `FileNotFoundError`), but that is not spec-visible.

**Sensor depth**: expanded (8 re-runs + 25 fresh; the feature writes user config files and confines file access)
**Result**: 30/33 killed, FAIL. 2 spec-level survivors (N17, N24), 1 out of spec (N20). All 8 re-runs killed.

---

## Probes (behaviour outside the tests)

1. Codex config without a final newline → valid TOML with the entry (HEAD correct; see N17).
2. The iteration-2 inline-table file now gets exit 2 with `cannot parse <file>: cannot add [mcp_servers.spinagram] (…); edit it by hand`, and the bytes are unchanged (`tests/test_mcp_install.py:270-272`).

---

## Code Quality

| Principle | Status |
|---|---|
| Minimum code / surgical | OK (iteration 3 touches `install.py` +10 lines and tests only) |
| Matches patterns | OK. `tomllib` is imported locally at `install.py:82` as well as inside `_toml` (minor duplication) |
| Spec-anchored outcome check | MCP-07 and INST-01 each have one weak case |
| Every test maps to an AC / edge / Done-when | OK (fix tests tagged T14–T16) |

---

## Ranked Gaps / Fix Tasks

1. **Minor, MCP-07: `select` on a styled spec is not compared to the CLI** (N24). Fix: in `tests/test_mcp_tools.py` (or `test_styles_select_filters`), copy `examples/styling` into the root and assert `t.styles(["styled.py"], select="edge") == json.loads(cli(… "check", styled.py, "--json", "--select", "edge"))`, plus `0 < len(...) < len(full)`.
2. **Minor, INST-01: no Codex append test on a file without a final newline** (N17). Fix: in `tests/test_mcp_install.py`, write `model = "o3"` (no `\n`), install, and assert the text starts with `model = "o3"\n` and `tomllib.loads(...)["mcp_servers"]["spinagram"] == entry`.

Both are test-only. HEAD behaviour is correct in both cases.

---

## Requirement Traceability Update

| Requirement | New status |
|---|---|
| MCP-01..06, 08..16 | Verified |
| MCP-07 | Needs test fix (gap 1) |
| INST-01 | Needs test fix (gap 2) |
| INST-02..10, HTTP-01, HTTP-02, DOC-01 | Verified |

---

## Summary

**Overall**: Not ready (FAIL), iteration 3 of 3. The fix-loop limit is reached, so this goes to the user. The defects found are two minor test gaps; no behaviour defect is known at HEAD.
**Spec-anchored check**: 27/29 ACs matched; 0 spec-precision gaps
**Sensor**: 30/33 killed (8/8 re-runs, 22/25 fresh; N20 is out of spec)
**Gate**: ruff clean; 752 passed, 3 skipped (pre-existing), 0 failed

**What works**: every iteration-1 and iteration-2 gap is fixed and pinned by a killing test. That covers root confinement, server defaults (theme, layout, formats), error results, logging, the write lock, resources, all six agent writers with both scopes and transports, Codex parse-after-edit safety, and both transports.

**validate_state**: `python3 …/tlc-spec-driven/scripts/validate_state.py mcp-server` → `ERROR mcp-server: validation.md verdict is FAIL - route the ranked gaps to fix tasks, then re-verify (feature is not done)` (exit 1, expected for a FAIL verdict)

**Lessons recorded**: L-047 (compare exactly to the reference on a non-empty fixture; N24) and L-048 (test text-appending writers on a file with no trailing newline; N17). N20 is out of spec, so no lesson.
