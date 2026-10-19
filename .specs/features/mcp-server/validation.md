# Validation: mcp-server - FAIL

**Verdict**: FAIL
**Result**: FAIL - 25/29 ACs matched; sensor 13/17 non-equivalent mutants killed (4 spec-level survivors; 1 equivalent excluded); gates green
**Date**: 2026-10-19
**Iteration**: 4 (extra pass approved by the user after the 3-iteration limit)
**Spec**: `.specs/features/mcp-server/spec.md`
**Diff range**: `b79feec..f9d8ea7` (branch `feat/mcp-server`, 22 commits; iteration-4 fix `eb302a7..f9d8ea7`, tests only)
**Verifier**: independent sub-agent (author != verifier)

FAIL on test strength only. T17 fixed both iteration-3 gaps: N24 and N17 are now killed. Four fresh mutants in spec-stated rules survived: G1 (prefix-based root check lets a sibling folder `root2` through; MCP-09), G5 (`--force` cannot replace a Codex entry whose name needs quoting; INST-08), G9 (error result carries a second text content; MCP-10) and G20 (the MCP `icons_search` default `limit` is 10, not 40; MCP-08). A probe shows HEAD behaves correctly in all four cases. Each fix is a test of a few lines.

## Iteration history

| Iteration | Verdict | Findings | Outcome |
|---|---|---|---|
| 1 (`..4e22dc1`) | FAIL | server theme outside the root broke every call; M5 (layout default), M26 (JSON indent 2) survived; Codex `--force` dropped a comment; `{"mcpServers": []}` traceback; MCP-10 shape undefined | T9–T13 |
| 2 (`..070e0b5`) | FAIL | F1 (server theme), F3 (`select`), F7 (previews vs `only`), F11 (`pack`) survived; inline `mcp_servers = {…}` written as invalid TOML | T14–T16 |
| 3 (`..320d0e6`) | FAIL | N17 (Codex file without final newline), N24 (`select` first match only) survived; N20 out of spec | T17 |
| 4 (this run) | FAIL | N17, N24 killed; G1, G5, G9, G20 survived (spec-level); N17b equivalent | gaps below |

---

## Task Completion

| Task | Status | Notes |
|---|---|---|
| T1–T16 | Done | verified in iterations 1–3 |
| T17 Exact select output, Codex file without final newline | Done | `tests/test_mcp_tools.py:210-215` (kills N24), `:218-230` (kills N17) |

Bookkeeping: T17's "Done when" checkboxes in `tasks.md` are still `[ ]`; the criteria are met (both mutants fail a test; build gate green).

---

## Spec-Anchored Acceptance Criteria

| ID | Spec-defined outcome | `file:line` + assertion | Result |
|---|---|---|---|
| MCP-01 | stdio server with the five tools | `tests/test_mcp_server.py:45` sorted names; `tests/test_mcp_cli.py:52` real stdio `["diagrams"] == 1` | PASS |
| MCP-02 | same files as `spinagram render`; root-relative `written` | `tests/test_mcp_tools.py:43-47`, `:52` | PASS |
| MCP-03 | one PNG per diagram, ≤4, diagram order | `tests/test_mcp_server.py:65`, `:67-68`, `:210` | PASS |
| MCP-04 | succeed with `preview needs spinagram[png]` | `tests/test_mcp_server.py:91`, `:93` | PASS |
| MCP-05 | `{"diagrams": n, "issues": [CLI strings]}` | `tests/test_mcp_tools.py:59-61`; G13 killed | PASS |
| MCP-06 | YAML text `spinagram layout` prints | `tests/test_mcp_tools.py:65` | PASS |
| MCP-07 | same JSON as `check --json`; optional `select` | `tests/test_mcp_tools.py:70`, `:73`, `:75`; `:214` `got == json.loads(cli(… "--select", "edge"))`, `:215` `len(got["elements"]) > 1`; N24 killed | PASS |
| MCP-08 | `["pack:name"]`, `pack`, `limit` default 40, as CLI | `tests/test_mcp_tools.py:90-93`; `tests/test_mcp_server.py:226-227` | GAP (minor): no test has more than 3 hits, so the default 40 is never observed; G20 (MCP default 10) survived |
| MCP-09 | `path outside root: <path>`, no file touched | `tests/test_mcp_tools.py:103`, `:105`, `:112`, `:161`; `tests/test_mcp_server.py:129` | GAP (minor): no case with a sibling folder sharing the root's name prefix; G1 (string-prefix check) survived |
| MCP-10 | `isError: true`, **one** text content equal to the CLI message, keeps serving | `tests/test_mcp_server.py:128-131` (checks `content[0]` only) | GAP (minor): the count of contents is never asserted; G9 (extra text content) survived |
| MCP-11 | `-t`/`--layout`/`--formats` are tool defaults; `-t` not root-checked | `tests/test_mcp_tools.py:136-139`, `:151-156`, `:190`, `:194`, `:206`; `tests/test_mcp_cli.py:104`; G12 killed | PASS |
| MCP-12 | missing extra: message, exit 2 | `tests/test_mcp_cli.py:36-37` | PASS |
| MCP-13 | one stderr line per call, clean stdout | `tests/test_mcp_server.py:145-149`; G8 killed | PASS |
| MCP-14 | later writing calls wait | `tests/test_mcp_server.py:179` `peak[0] == 1` | PASS |
| MCP-15 | resources listed with descriptions | `tests/test_mcp_server.py:186`; G15 killed | PASS |
| MCP-16 | SKILL.md text, `text/markdown` | `tests/test_mcp_server.py:189-190` | PASS |
| INST-01 | stdio entry, create dirs, `installed <name> in <file>` | `tests/test_mcp_install.py:70-71`, `:84`, `:168-171`; `tests/test_mcp_cli.py:141`; `tests/test_mcp_tools.py:229-230` (no final newline); N17, G4 killed | PASS |
| INST-02 | `--user` file | `tests/test_mcp_install.py:70`, `:79-81`; `tests/test_mcp_cli.py:149`; G10 killed | PASS |
| INST-03 | one entry per `-a` | `tests/test_mcp_cli.py:156` | PASS |
| INST-04 | flags after `mcp`, absolute `--root`/theme folder, built-in name kept | `tests/test_mcp_install.py:59-60`; `tests/test_mcp_tools.py:170-171`; G11 killed | PASS |
| INST-05 | `sys.executable -m spinagram mcp`; `--uvx` pinned | `tests/test_mcp_install.py:50-53`; `tests/test_mcp_cli.py:13`, `:169` | PASS |
| INST-06 | HTTP entry per AGENT table | `tests/test_mcp_install.py:91`, `:99`, `:191` | PASS |
| INST-07 | other keys/servers/text kept | `tests/test_mcp_install.py:110-111`, `:130`, `:181`, `:209`, `:237`, `:272`; G3, G6 killed | PASS |
| INST-08 | exit 1 + message; `--force` replaces that entry | `tests/test_mcp_install.py:120-121`, `:201-209`; `tests/test_mcp_cli.py:180-185` | GAP (minor): `--force` is only tested on a bare-key name; G5 (replace cannot find a quoted `[mcp_servers."my diagrams"]` table) survived |
| INST-09 | exit 2 `cannot parse <file>: <reason>`, unchanged | `tests/test_mcp_cli.py:191-193`, `:208-209`; `tests/test_mcp_install.py:138-140`, `:250`, `:258-260`, `:270-272` | PASS |
| INST-10 | unknown/missing agent → exit 2 listing agents | `tests/test_mcp_cli.py:198-202`; `tests/test_mcp_install.py:145` | PASS |
| HTTP-01 | streamable HTTP `/mcp`, 127.0.0.1 | `tests/test_mcp_cli.py:80`, `:105` | PASS |
| HTTP-02 | non-loopback warning on stderr | `tests/test_mcp_cli.py:117-120` | PASS |
| DOC-01 | `## MCP server` section: tools, install, root rule | `src/spinagram/agent_skills/spinagram/SKILL.md:242`, `:246-257` | PASS |

Count: 25/29 ACs matched. MCP-08, MCP-09, MCP-10 and INST-08 each have one weak case. No spec-precision gaps.

---

## Edge Cases

| Edge case | Evidence | Result |
|---|---|---|
| empty / no diagram → `no diagrams found` | `tests/test_mcp_tools.py:118-121`; `tests/test_mcp_server.py:128`; G2 killed | PASS |
| other preview failure → `preview failed: <first line>` | `tests/test_mcp_server.py:103` | PASS |
| relative `out` under root; absolute outside → MCP-09 | `tests/test_mcp_tools.py:51-53`, `:99` | PASS |
| symlink pointing outside → MCP-09 | `tests/test_mcp_tools.py:112` | PASS |
| large `~/.claude.json`: same values, indent 2 | `tests/test_mcp_install.py:111`, `:226-227`; G14 killed | PASS |

---

## Gate Check

- **Lint**: `set -o pipefail; uv run ruff check src tests examples` → `All checks passed!` (exit 0)
- **Build**: `set -o pipefail; uv run --all-extras pytest -q` → **754 passed, 3 skipped**, 0 failed (exit 0)
- **Feature tests**: 85 passed (4 files)
- **Skipped**: the same 3 pre-existing skips (dot runtime ×2, soffice)
- **Test count**: 752 → 754 (+2 T17 tests); none removed or weakened (`git diff eb302a7..HEAD -- tests` adds lines only)

---

## Discrimination Sensor

Scratch: `git -C mcpwt worktree add --detach …/scratchpad/verify-mcp4 HEAD`. The import path was confirmed (`spinagram.__file__` under `verify-mcp4/src`) and the baseline was 85 passed. Each mutant was an exact-string replacement (asserted to occur once), run with `PYTHONPATH=verify-mcp4/src uv run --project mcpwt --all-extras python -m pytest -q -p no:cacheprovider tests/test_mcp_{tools,server,install,cli}.py`, then reverted with `git checkout`. The scratch was removed with `git worktree remove --force`. `git -C mcpwt status --porcelain` matched the baseline (`?? web/node_modules`) before and after.

### Re-runs (iteration-3 survivors)

| # | Mutation | Result | Killed by |
|---|---|---|---|
| N24 | `tools.py:80` `select` keeps the first match only (`[...][:1]`) | Killed | `test_styles_select_equals_the_cli` |
| N17 | `install.py:130` append `text + table` | Killed | `test_codex_file_without_final_newline` |
| N17b | `install.py:130` keep the line break, drop the blank separator line | Survived, equivalent | - |

### Fresh mutants (not tried in iterations 1–3)

| # | File | Mutation (rule) | Result | Killed by |
|---|---|---|---|---|
| G1 | `tools.py:25` | `str(q).startswith(str(root))` instead of `is_relative_to` (MCP-09) | **Survived** | - |
| G2 | `tools.py:40` | `if diagrams is None` (edge: `no diagrams found`) | Killed | `test_cli_error_messages`, 2 server tests |
| G3 | `install.py:130` | Codex append drops the existing text (INST-07) | Killed | `test_codex_keeps_other_text` +2 |
| G4 | `install.py:92` | Codex parent folders not created (INST-01) | Killed | `test_codex_new_file[*]` +2 |
| G5 | `install.py:134` | replace regex knows only the bare-key spelling (INST-08) | **Survived** | - |
| G6 | `install.py:107` | `--force` clears the other servers (INST-08 "that entry only") | Killed | `test_force_replaces_only_the_entry` |
| G8 | `server.py:47` | log line names `tool`, not the tool (MCP-13) | Killed | `test_one_log_line_per_call_on_stderr` |
| G9 | `server.py:45` | error result gets a second text content (MCP-10) | **Survived** | - |
| G10 | `cli.py:408` | `--user` not passed to `install` (INST-02) | Killed | `test_install_user_scope` |
| G11 | `install.py:37` | `-t` always made absolute (INST-04 built-in name) | Killed | `test_server_args` +2 |
| G12 | `cli.py:384` | `--root` ignored by `spinagram mcp` (MCP-09 root) | Killed | `test_flags_reach_the_server`, `test_http_server_answers` |
| G13 | `tools.py:59` | issues as `repr` (MCP-05) | Killed | `test_check_matches_the_cli` |
| G14 | `install.py:109` | JSON without final newline (edge: rewrite) | Killed | `test_json_text_is_indented_two` |
| G15 | `server.py:93` | only the first skill is a resource (MCP-15) | Killed | `test_skills_are_resources` |
| G20 | `server.py:90` | MCP `icons_search` default `limit` 10 (MCP-08) | **Survived** | - |

### Survivor classification

- **N17b: equivalent.** The result is `model = "o3"\n[mcp_servers.spinagram]…`: valid TOML, entry present, other text unchanged. The spec does not require a blank line between tables.
- **G1: gap (MCP-09).** Probe: root `…/root`, file `…/root2/x.yaml`, call `check(["../root2/x.yaml"])`. HEAD returns `path outside root: ../root2/x.yaml`. The mutant checks and returns the file's issues. No test uses a sibling folder whose name starts with the root's name.
- **G5: gap (INST-08).** Probe: `install("codex", name="my diagrams")` and then the same call with `force=True`. HEAD writes `[mcp_servers."my diagrams"]` with the new `url`. The mutant raises `cannot parse …: my diagrams is not a [mcp_servers.my diagrams] table`. `--force` is only tested with `spinagram`.
- **G9: gap (MCP-10).** Probe: `check` with `paths=[]` over the protocol. HEAD returns 1 content. The mutant returns 2 (`['no diagrams found', 'spinagram: error']`). The test reads `content[0]` only.
- **G20: gap (MCP-08).** Probe: a pack with 45 matching icons, and `icons_search` called with no `limit`. HEAD returns 40 hits and the mutant returns 10. Every test has 3 hits or fewer.

**Sensor depth**: expanded (3 re-runs + 15 fresh; the feature writes user config files and confines file access)
**Result**: 13/18 killed (13/17 excluding the equivalent N17b), FAIL. 4 spec-level survivors (G1, G5, G9, G20).

---

## Code Quality

| Principle | Status |
|---|---|
| Minimum code / surgical | OK (iteration 4 adds 24 test lines and touches no source) |
| Matches patterns | OK. The T17 tests sit in `test_mcp_tools.py`, though the Codex test belongs with `test_mcp_install.py` (cosmetic) |
| Spec-anchored outcome check | 4 weak cases (MCP-08, MCP-09, MCP-10, INST-08) |
| Every test maps to an AC / edge / Done-when | OK (T17 tests tagged) |
| Guidelines | none specific; strong defaults applied |

---

## Ranked Gaps / Fix Tasks

1. **Minor, MCP-09: sibling folder sharing the root's prefix** (G1). In `tests/test_mcp_tools.py`, add `tmp_path/"root2"/x.yaml` and assert `Tools(root).check(["../root2/x.yaml"])` raises `^path outside root: ../root2/x.yaml$`.
2. **Minor, MCP-10: exactly one text content** (G9). In `tests/test_mcp_server.py:128`, assert `len(bad.content) == 1` (and the same for `outside`).
3. **Minor, INST-08: `--force` on a quoted Codex name** (G5). In `tests/test_mcp_install.py`, install codex with `name="my diagrams"`, then with `url=URL, force=True`, and assert `tomllib.loads(text)["mcp_servers"]["my diagrams"] == {"url": URL}`, with exactly one such table.
4. **Minor, MCP-08: default `limit` 40 through MCP** (G20). In `tests/test_mcp_server.py`, register a pack with 45 matching icons, call `icons_search` with no `limit` and assert 40 results. Do the same for `Tools.icons_search`.

All four are test-only. HEAD behaviour is correct in each case (probes above).

---

## Requirement Traceability Update

| Requirement | New status |
|---|---|
| MCP-01..07, 11..16 | Verified |
| MCP-08, MCP-09, MCP-10 | Needs test fix (gaps 4, 1, 2) |
| INST-01..07, 09, 10, HTTP-01, HTTP-02, DOC-01 | Verified |
| INST-08 | Needs test fix (gap 3) |

---

## Summary

**Overall**: Not ready (FAIL), iteration 4. No behaviour defect is known at HEAD. The four gaps are missing assertions.
**Spec-anchored check**: 25/29 ACs matched; 0 spec-precision gaps
**Sensor**: 13/18 killed (re-runs: N24, N17 killed, N17b equivalent; fresh: 11/15 killed, 4 survived)
**Gate**: ruff clean; 754 passed, 3 skipped (pre-existing), 0 failed

**What works**: T17 closes N24 and N17. All earlier fixes remain pinned. That covers root confinement (including symlinks), server defaults, error results, logging, the write lock, resources, all six agent writers in both scopes and both transports, Codex parse-after-edit safety, and both transports.

**validate_state**: `python3 …/tlc-spec-driven/scripts/validate_state.py mcp-server` → `ERROR mcp-server: validation.md verdict is FAIL - route the ranked gaps to fix tasks, then re-verify (feature is not done)` (exit 1, expected for a FAIL verdict)

**Lessons recorded**: L-049 (G1, sibling-prefix confinement), L-050 (G20, observable defaults), L-051 (G9, assert exact length), L-052 (G5, quoted names on replace paths). N17b is equivalent, so no lesson.

---

## Acceptance (2026-10-19, user decision)

Pass 4 failed on 4 test-only gaps (G1, G9, G5, G20); the probes showed the code correct in every case. The user chose
to add the tests and release without a 5th pass. T18 adds them; each of G1, G9, G5 and G20 was re-applied in a scratch
worktree and now fails `tests/test_mcp_server.py`. The verdict above stays FAIL because no independent pass ran after
T18: the feature is accepted by the user, not verified.

Note: lesson ids recorded on `feat/mcp-server` (L-040…L-052) were renumbered L-049…L-061 when the branch was merged into `feat/excalidraw-mcp`, because the Excalidraw verifications had taken L-040…L-048.
