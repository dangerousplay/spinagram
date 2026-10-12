# Annotations Validation

## Validation: annotations - PASS

**Date**: 2026-10-12
**Spec**: `.specs/features/annotations/spec.md`
**Diff range**: `main..HEAD` (main = `4af7080`; spec commit `a3ab1df` through `a29d02f`)
**Verifier**: independent sub-agent (author ≠ verifier)
**Iteration**: 2 of 3. Iteration 1 (at `2698f63`) found 8 surviving mutants and 1 spec-precision gap. Commit
`138fe7e` closed them with tests only, and `a29d02f` pinned the ANN-01 order. Source under `src/` is unchanged
since `2698f63`.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1-T17 | ✅ Done | commits `960614f`..`2698f63` |
| T18 | ✅ Done | verifier test gaps, `138fe7e` |
| T19 | ✅ Done | ANN-01 wording, `a29d02f` |

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| ANN-01 | each class/style once; node classes and styles in node order first, then edge classes in edge order; humanised | `tests/test_annotations.py:248` - `got == [(".web","Web",...),(".edge-svc","Edge svc",...),("style:dark","Dark",...),("edge.async","Async",...),("edge.replication","Replication",...)]` | ✅ (amended wording matches the asserted order) |
| ANN-02 | exactly the given items, order, labels | `tests/test_annotations.py:58` - `list(lg.items.items()) == [...]`; `:260` entries | ✅ |
| ANN-03 | `legend: unused entry '<key>'`; still drawn from the theme default | `tests/test_annotations.py:710` - exact issue string; `:958` - `(sw.fill, sw.stroke) == (st["fill"], st["stroke"])` | ✅ |
| ANN-04 | swatch fill/stroke/width/dash of first node; radius × swatch h / node h | `tests/test_annotations.py:390-391` - `== ("#FEE2E2","#DC2626",4,node.dash,True)`; `radius == approx(6 * sw.h / node.h)` | ✅ |
| ANN-05 | sample colour, width, dash, end markers | `tests/test_annotations.py:401-403` - `== ("#F59E0B", 2, [5.0, 4.0], "circle", "open-arrow")` | ✅ |
| ANN-06 | icon at swatch size | `tests/test_annotations.py:415` - `sw.icon.path == icon and sw.fill is None` | ✅ (size not asserted; cosmetic) |
| ANN-07 | titled card "Legend" in band | `tests/test_annotations.py:427-428` - `(card.x, card.y, card.w) == (ax + aw - 360, ay, 360)`; `title.block.lines == ["Legend"]` | ✅ |
| ANN-08 | area minus right band (360 + 32) | `tests/test_annotations.py:315` - `_area(d, t) == (x, y, w - 392, h)`; `:805` custom area | ✅ |
| ANN-09 | area minus bottom band (panel height + 32) | `tests/test_annotations.py:903` - `_area(d, t) == (ax, ay, aw, ah - (legend_h + 32))` | ✅ |
| ANN-10 | right panel 360; bottom band spans area width | `tests/test_annotations.py:277` - `== ("right", 392)`; `:905` - `(card.x, card.w, card.h) == (ax, aw, legend_h)`; `:920-921` shared with steps | ✅ |
| ANN-11 | `annotations: overflow` with excess px | `tests/test_annotations.py:936` - `f"P1:annotations: overflow — panels exceed the band by {excess}px" in _issues(d)` | ✅ |
| ANN-12 | manual layout: `annotations: overlap` per intersected node/zone | `tests/test_annotations.py:734` - `== ["M1:annotations: overlap — the band covers 'right'"]`; `:794` | ✅ |
| ANN-13 | edge badge + panel row | `tests/test_annotations.py:477`, `:488`, `:629`, `:768` | ✅ |
| ANN-14 | node badge on top-left corner | `tests/test_annotations.py:496` - `== (node.x, node.y)` | ✅ |
| ANN-15 | next after highest; explicit n kept | `tests/test_annotations.py:24` - `== [(1,..),(2,..),(7,..),(8,..)]` | ✅ |
| ANN-16 | `steps: duplicate number <n>` | `tests/test_annotations.py:718` - exact string | ✅ |
| ANN-17 | ascending; identical badges | `tests/test_annotations.py:442`, `:505` | ✅ |
| ANN-18 | beside label, no overlap | `tests/test_annotations.py:474-476` | ✅ |
| ANN-19 | YAML `a -> b` → first a→b edge; unknown ref fails naming it | `tests/test_annotations.py:945` - `d.step("x", on=(a, b)).edge == 1`; `:951` YAML `.edge == 1`; `:143` `raises(ValueError, match=message)` | ✅ |
| ANN-20 | bubble text/title, leader to nearest side | `tests/test_annotations.py:553-556` | ✅ |
| ANN-21 | kind colour token + glyph | `tests/test_annotations.py:565-567` (4 kinds) | ✅ |
| ANN-22 | first free of top/right/bottom/left; avoids nodes, zones, panels, callouts | `tests/test_annotations.py:577-580`; `:588` callouts; `:874-875` legend panel; `:888-889` zones; `:832` slide | ✅ |
| ANN-23 | explicit side | `tests/test_annotations.py:596` | ✅ |
| ANN-24 | first side + `callout: overlap` naming node | `tests/test_annotations.py:604`, `:740` | ✅ |
| ANN-25 | invalid kind fails naming kinds | `tests/test_annotations.py:80`, `:150` | ✅ |
| ANN-26 | card 6 px primary bar left | `tests/test_annotations.py:672` - `(bar.x, bar.w, bar.fill) == (card.x, 6, t.color("primary"))` | ✅ |
| ANN-27 | quote mark + italic body | `tests/test_annotations.py:681-684` | ✅ |
| ANN-28 | sticky unchanged | `tests/test_annotations.py:692-695` | ✅ |
| ANN-29 | invalid variant fails naming variants | `tests/test_annotations.py:94`, `:148` | ✅ |
| ANN-30 | note icon like node icon | `tests/test_annotations.py:675` | ✅ |
| ANN-31 | legend card uses CSS fill/stroke/radius/shadow | `tests/test_annotations.py:853` - `(card.fill, card.stroke, card.radius) == ("#111827", "#374151", 4) and card.shadow is not None` | ✅ |
| ANN-32 | every badge (diagram + panel) uses `step`, `step::label` | `tests/test_annotations.py:857` - `(b.fill, b.stroke, b.label.blocks[0].color) == ("#7C3AED", "#4C1D95", "#FFFFFF")` for `step-0/1`, `steps-0/1` | ✅ |
| ANN-33 | `callout.warning` fill/stroke; `::title`, `::body` | `tests/test_annotations.py:858-860` drawn bubble; `:202-204` computed | ✅ |
| ANN-34 | `note.card` matches | `tests/test_annotations.py:205` | ✅ |
| ANN-35 | inspector lists annotation elements with rules | `tests/test_annotations.py:213-218` (via `css.inspect`, the CLI's backing call) | ✅ |
| ANN-36 | AWS legends + steps | `examples/showcase/aws_three_tier.py:38-51`; `examples/showcase/aws_network_hub.py:42-49` | ✅ |
| ANN-37 | K8s/GCP callout + legend | `examples/showcase/k8s_platform.py:49-50`; `examples/showcase/k8s_networking.py:46-48`; `examples/showcase/gcp_global_app.py:45-47` | ✅ |
| ANN-38 | notes slide, three variants | `examples/showcase/notes.py:11-21` | ✅ |
| ANN-39 | showcase check 0 issues | `spinagram check examples/showcase` → `6 diagram(s), 0 issue(s)`; `tests/test_metadata.py:206` | ✅ |

**Status**: ✅ All 39 ACs covered with discriminating evidence; no open spec-precision gaps.

---

## Discrimination Sensor

Fresh detached `git worktree` at `a29d02f` in the scratchpad. `import spinagram` resolved to
`<wt>/src/spinagram/__init__.py`. Each mutant ran `uv run --project <wt> --all-extras pytest -q -x tests` with
`PYTHONDONTWRITEBYTECODE=1` and `__pycache__` cleared beforehand. `tests/test_web_unit.py` was deselected in the
worktree only: it needs the untracked `web/node_modules`, and it passes in the real tree. Worktree baseline: 463
passed. Mutants are the same 41 as iteration 1, plus M42 for the new zone clause.

| # | File | Mutation | Killed by |
| - | ---- | -------- | --------- |
| M01-M04 | `src/spinagram/annotate.py:30-82` | entry order, dedupe, humanize ×2 | ✅ `tests/test_annotations.py:248` |
| M05 | `src/spinagram/annotate.py:75` | unused flag always True | ✅ `:260` |
| M06 | `src/spinagram/annotate.py:161` | right band without gap | ✅ `:277` |
| M07 | `src/spinagram/annotate.py:169` | bottom band without gap | ✅ `:903` (iteration 1 survivor) |
| M08, M09 | `src/spinagram/autolayout/__init__.py:259,261` | `_area` reservation dropped | ✅ `:315`, `:330` |
| M10-M12 | `src/spinagram/annotate.py:256-258` | swatch radius/dash/width | ✅ `:390-391` |
| M13 | `src/spinagram/annotate.py:245` | sample marker_end | ✅ `:401` |
| M14-M16 | `src/spinagram/annotate.py:359-380` | badge placement ×3 | ✅ `:474`, `:488`, `:496` |
| M17 | `src/spinagram/model.py:499` | numbering = count + 1 | ✅ `:24` |
| M18-M20 | `src/spinagram/annotate.py:387-448` | side order, alignment, overlap issue | ✅ `:577`, `:832`, `:604` |
| M21 | `src/spinagram/annotate.py:285` | legend panel not an obstacle | ✅ `:874` (iteration 1 survivor) |
| M22 | `src/spinagram/annotate.py:385` | tip colour → primary | ✅ `:565` |
| M23-M25 | `src/spinagram/annotate.py:494-498` | duplicate threshold, overflow off, overlap on laid-out | ✅ `:718`, `:726`, `tests/test_metadata.py` CLI |
| M26-M29 | `src/spinagram/layout.py:144-188` | accent 4 px, quote italic/order, sticky as card | ✅ `:672`, `:684`, `:692` |
| M30-M32 | `src/spinagram/css.py:544-567` | step key, callout kind class, sticky class | ✅ `:192` test |
| M33, M34 | `src/spinagram/yaml_io.py:115,121` | `on`→`True` key, `a -> b` reversed | ✅ `:125` test |
| M35 | `src/spinagram/annotate.py:207` | legend/steps card ignores CSS | ✅ `:853` (iteration 1 survivor) |
| M36 | `src/spinagram/annotate.py:228` | step badge ignores CSS | ✅ `:857` (iteration 1 survivor) |
| M37 | `src/spinagram/annotate.py:496` | overflow excess +100 px | ✅ `:936` (iteration 1 survivor) |
| M38 | `src/spinagram/model.py:492` | pair picks last a→b edge | ✅ `:945` (iteration 1 survivor) |
| M39 | `src/spinagram/annotate.py:255` | unused swatch fill None | ✅ `:958` (iteration 1 survivor) |
| M40 | `src/spinagram/annotate.py:344` | bottom legend half width | ✅ `:905` (iteration 1 survivor) |
| M41 | `src/spinagram/annotate.py:472` | leader to far side | ✅ `:555` |
| M42 | `src/spinagram/annotate.py:442` | zones never obstacles | ✅ `:888` (new) |

**Sensor depth**: expanded (42 manual behaviour mutants)
**Sensor outcome**: 42/42 killed, 0 survived - PASS

Isolation: `git worktree remove --force` and `prune`. The real tree's `git status --porcelain` matched the
pre-sensor baseline, which held only the verifier's `.specs` files. No `git stash` was used.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ |
| Surgical changes | ✅ (unannotated scenes unchanged, `tests/test_annotations.py:632`) |
| No scope creep | ✅ |
| Matches patterns | ✅ |
| Spec-anchored outcome check (asserted values match spec) | ✅ |
| Per-layer Coverage Expectation met | ✅ |
| Every test maps to a spec requirement | ✅ |
| Documented guidelines followed: `pyproject.toml` (pytest, ruff); otherwise strong defaults applied | ✅ |

Notes, both non-blocking:
- tasks.md T8 says the badge goes at the label's right edge, but `src/spinagram/annotate.py:374` puts it before
  the label. ANN-18 says "beside", so this complies.
- `examples/showcase/k8s.css:44` has an unused `step` selector. It is reported as info, not as an issue.

---

## Edge Cases

- [x] Steps without legend take the band alone - `tests/test_annotations.py:292`
- [x] Tall legend falls back to one column when labels do not fit two - `tests/test_annotations.py:808`
- [x] Callout on another diagram's node fails - `tests/test_annotations.py:86`
- [x] PowerPoint annotations are native editable shapes - `tests/test_annotations.py:765-768`

---

## Gate Check

- **Gate command**: `set -o pipefail; uv run ruff check src tests && uv run pytest -q && uv run spinagram check examples/showcase`
- **Outcome**: ruff clean; 464 passed, 0 failed, 3 skipped; showcase `6 diagram(s), 0 issue(s)`
- **Test count before feature**: 393 collected (main `4af7080`)
- **Test count after feature**: 467 collected
- **Delta**: +74 (`tests/test_annotations.py`; `tests/test_metadata.py:206` extended for NOTE01)
- **Skipped tests**: three skips that predate this feature and depend only on the environment: `tests/test_autolayout.py:155`, `:165` (dot not installed) and `tests/test_pptx_svg.py:129` (soffice not installed)
- **Failures**: none

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| ANN-01 .. ANN-39 | Implementing / Needs Fix | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready

**Spec-anchored check**: 39/39 ACs matched their spec outcomes; 0 spec-precision gaps
**Sensor**: 42/42 mutations killed
**Gate**: 464 passed, 0 failed, 3 skipped (environment-only skips that predate this feature)

**Fixes since iteration 1**: tests now check drawn CSS, panel and zone obstacles, bottom band size and width,
the exact overflow excess, the first parallel edge, and theme-default drawing of unused entries. ANN-01 now
states the cross-type order.

**Lessons**: L-010..L-015 were recorded from the iteration-1 signals. This iteration adds no new signal.
