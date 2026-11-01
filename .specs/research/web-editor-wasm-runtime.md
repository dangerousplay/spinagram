# Web editor on WebAssembly: RustPython vs Pyodide, with canvas edits from YAML or Python

Date: 2026-11-01. Status: research, no code changed. Follows `rust-engine-evaluation.md` (which covered Pyodide
as option A but not RustPython) and builds on the untracked `features/canvas-editor/spec.md`.

Legend: **[V]** verified on 2026-11-01 (repo, RustPython source at `123dece`, GitHub API). **[A]** assumed or
estimated, not measured.

---

## 1. Verdict

- **Yes, it can work.** The engine can run in the browser in a Web Worker, with Python (YAML or Python specs) on
  WASM and the Rust core linked in. The canvas then edits YAML and Python specs, not YAML only.
- **RustPython is feasible but unproven for this load.** The pure-Rust toolchain is its best point: the
  interpreter and `spinagram-core` go into one `wasm32` binary built with wasm-bindgen. That needs no
  Emscripten, no nightly Rust and no pin to a Pyodide ABI. Its weak points are speed and maturity:
  - its own contributors say it is slower than CPython;
  - its WASM README still calls support "preliminary";
  - the npm package `rustpython_wasm` is a 2022 pre-alpha, so we would build our own wasm crate.
- **Pyodide is the safer runtime.** It runs real CPython and ships Pillow and PyYAML prebuilt. Its cost is
  `_core`: that needs an Emscripten wheel built with Pyodide's exact emsdk and a nightly Rust toolchain, re-pinned
  on each Pyodide release.
- **Pick the runtime by measurement, not by preference.** Run a two-runtime spike with hard go criteria
  (section 6). My prior [A]: Pyodide passes the speed gate and RustPython wins on bundle size and toolchain.
- **The canvas does not need Python on the drag path.** Dragging is a client overlay at 60 fps. The engine runs
  on release, wherever it runs. Moving the engine into the browser removes the server round-trip, and also
  allows:
  - static hosting, i.e. a docs playground with no server;
  - running Python specs sandboxed in the browser, instead of executing them on the serve process.
- **Python positions become editable** through call-site spans plus `ast` source-range patching (section 4).
  Both runtimes support this. When a spec computes its positions (loops, variables), a **position override**
  layer takes the edit instead. The same layer also lets users nudge engine-laid-out diagrams.

---

## 2. What the engine needs from a browser runtime

From `src/spinagram` [V]:

| Need | Where | RustPython | Pyodide |
|---|---|---|---|
| Stdlib: dataclasses, functools, typing, pathlib, re, json, copy, math, html, hashlib, unicodedata, tomllib, warnings, contextlib, importlib, io, collections, zipfile, tarfile, urllib | engine-wide | All present (`Lib/` or Rust stdlib) [V] | All present (CPython) |
| PyYAML | `yaml_io.py`, `yamlload.py`, `icons.py`, `theme.py` | Pure-Python fallback only (no libyaml C loader); slower [A] | Prebuilt package |
| Pillow | `css.py:18` (`ImageColor`, **top-level import**), `text.py:20` (Python measure path), `engine/icons.py:25` (raster icons, lazy) | **Not available** (C extension). `css.py` must stop importing it at module load; colour parsing must go through the Rust cascade or a small pure parser | Prebuilt package |
| fontTools | `text.py:29` (cmap), `backends/fontsubset.py`, `backends/figma.py` | Pure Python, imports, heavy [A] | Pure Python |
| tinycss2 | `css.py` (Python cascade) | Pure Python | Pure Python |
| Rust core `_core` | `rust.py` (text, route, SVG, PNG, CSS) | Native module via `rustpython-vm` `#[pymodule]` + `Interpreter::builder().add_native_module(..)` [V, `crates/wasm/src/vm_class.rs:79-109`]. A second thin adapter beside `spinagram-core-py/src/lib.rs` (181 lines, coarse JSON/string API) | Emscripten wheel: maturin + pinned emsdk + nightly Rust (`-Z emscripten-wasm-eh`) per Pyodide ABI; abi3 on Emscripten is unsettled |
| `ast` with end offsets, `sys._getframe` | Python write-back (section 4) | Present [V, `crates/vm/src/stdlib/_ast.rs`, `sys.rs:1186`] | Present |
| Subprocess layouts: dot, d2, ELK via Node | `autolayout/engines/*` | Break. ELK can run as elkjs in JS through the runtime's JS bridge | Same |
| Icon pack download (`urllib`) and disk cache | `icons.py` | Host fetches and caches packs in IndexedDB, then passes bytes in | Same |
| Fonts | `fonts/`, theme fonts | Bundled bytes only; there are no system fonts in WASM | Same |

RustPython also ships `crates/capi`, a minimal CPython C-API shim with a PyO3 config (`target_abi=RustPython-abi3t-3.15`) [V]. It is a native `cdylib` and does not help in WASM, but it shows the PyO3 adapter could be reused natively later.

---

## 3. Architecture (either runtime)

```
main thread (React)                         Web Worker
┌───────────────────────────┐   source,    ┌──────────────────────────────────────┐
│ CodeMirror  ◄─ text ──────┤   kind,      │ Python runtime (RustPython | Pyodide) │
│ Canvas: rendered SVG      │   files ───► │   spinagram (pure Python)             │
│   + interaction overlay   │              │   spinagram._core (Rust, same .wasm   │
│   (hit-test on scene JSON)│ ◄─ svg,      │   or Emscripten wheel)                │
│ Patchers: YAML (eemeli)   │   scene,     │   elkjs bridge (optional)             │
│           Python (spans)  │   srcmap,    └──────────────────────────────────────┘
│ Serve API or File System  │   diagnostics
│   Access for read/write   │
└───────────────────────────┘
```

- Drag, resize and guides run on the overlay, using the scene geometry (`scene_json.py` already gives it). Nothing
  waits for the engine until release.
- On release the patcher rewrites the source text. The worker re-renders, and the SVG and scene replace the old
  ones. CodeMirror shows the patched text (as canvas-editor YAML-06 requires).
- The worker returns a **source map**: element id → source span. The YAML loader gets it from the parser marks;
  the Python model gets it from call sites. Edits use it to find what to patch.
- `spinagram serve` keeps file I/O, watch and packs. A static build uses the File System Access API or in-memory
  files.

---

## 4. Edits from the canvas, by source kind

### YAML
Unchanged from the canvas-editor spec: patch with eemeli `yaml` (`parseDocument` and `String(doc)`), which
keeps comments. No runtime is involved.

### Python (new: canvas-editor currently says read-only)
1. When `Diagram.box/zone/edge/...` is called, the model records the caller's `(file, lineno, col, end_lineno,
   end_col)` using `sys._getframe(1)` and the frame's code positions. The scene JSON carries it as `src`.
2. On a canvas move or resize, the worker runs `ast.parse` on the spec and finds the `Call` node whose span
   matches. Then:
   - **Literal kwargs** `x=`, `y=`, `w=`, `h=` (numbers): replace their source range. Everything else stays
     byte-identical.
   - **Missing kwargs**: insert them before the closing paren, following the call's existing style (same line or
     one per line).
   - **Computed positions**: a loop (one call site, many nodes), a variable, an expression, or a helper function
     that builds nodes. Refuse the source patch and write a position override instead (below), with the hint
     "Position computed in code; saved as an override".
3. Renames work the same way when the title is a string literal; otherwise they become overrides.

Both runtimes provide `ast` with end offsets and `sys._getframe`, so libcst is not needed.

### Position overrides (any source, including engine layouts)
- A sidecar file, `<spec>.layout.yaml`, maps a diagram id to node or zone ids, each with `x`, `y`, `w`, `h`. The
  engine applies it after the spec and the autolayout, before routing.
- It covers computed Python positions and engine-laid-out diagrams. canvas-editor SEL-07 disables moves for
  those today.
- Trade-off: positions live outside the source. The UI must show which nodes are overridden and offer
  "Bake into source" where patching is possible and "Clear override" everywhere.

---

## 5. Risks

| Risk | Runtime | Severity | Mitigation |
|---|---|---|---|
| Interpreter speed: `software_architecture.yaml` builds its scene in 157–245 ms on CPython [V, prior doc]; RustPython in WASM could be several times slower [A] | RustPython | High | Measure it in the spike. The Rust core already takes text, route, SVG and CSS off Python. Next candidates are the layered engine and the YAML loader |
| Semantics gaps, e.g. dataclass, typing or regex edge cases | RustPython | Medium | Run the 2,800-test suite natively under RustPython (`SPINAGRAM_RUST=0` minus the Pillow paths) before any WASM work. The pass rate is the compatibility number |
| No Pillow | RustPython | Medium | Make Pillow lazy in `css.py`. Use the Rust core for measure and colour. Raster icons go through the host (browser `createImageBitmap`) or resvg |
| Pyodide ABI churn for `_core` (emsdk and nightly Rust pin, abi3 unsettled) | Pyodide | Medium | A separate CI job builds against the current Pyodide release and pins the Pyodide version in the web app |
| Bundle size: Pyodide is about 10 MB plus packages [A, prior doc]; RustPython with a frozen stdlib is unknown (its `Lib/` is 53 MB of source; freeze only the modules used) [V/A] | both | Medium | Lazy-load the worker after first paint; keep the server render while it loads |
| WASM build of RustPython is "preliminary"; no maintained npm package | RustPython | Medium | Own crate `rust/spinagram-wasm` on `rustpython-vm` with `freeze-stdlib`, like RustPython's own `crates/wasm` |
| dot and d2 layouts unavailable in the browser | both | Low | Fall back to the server render for those diagrams; ELK goes through elkjs |
| Running untrusted Python | both | Positive | In the browser this is sandboxed by the page. It is safer than `serve` executing specs |

---

## 6. Recommended spike and go criteria

Spec: `.specs/features/wasm-editor-runtime/spec.md`. In short:

1. **Native RustPython compatibility (cheap, first).** Build `rustpython` and run the test suite on it.
   Go: ≥ 95 % pass, with failures limited to Pillow and subprocess paths.
2. **Two worker prototypes**: RustPython + `_core` (wasm-bindgen) and Pyodide + `_core` (Emscripten wheel). Each
   renders `quickstart.yaml`, `aws_layout.yaml` and `software_architecture.yaml`, plus one Python spec.
3. **Measure** for each:
   - cold start;
   - transfer bytes (gzip);
   - warm render (p50 and p95 of 20 runs);
   - SVG byte-equality with native output.
4. **Pick**:
   - RustPython if warm p95 ≤ 300 ms on `software_architecture.yaml`, gzip ≤ 8 MB and SVGs are identical;
   - otherwise Pyodide if it meets the same criteria;
   - otherwise neither, and keep the server render (option B in the prior doc).

Not done here: building RustPython locally was blocked by the session's permission policy (it runs external
build scripts). The spike needs that permission.

---

## 7. Interaction with the canvas-editor spec (user decisions to revisit)

The untracked `features/canvas-editor/` spec records three choices this evaluation would change. They are the
user's to make; this doc does not edit that spec.

| canvas-editor decision | This evaluation suggests |
|---|---|
| Server-rendered SVG + overlay | Keep the overlay. The render source becomes the worker, and the server is the fallback |
| Python specs read-only, "Export as YAML" | Python is editable through span patching, with overrides for computed positions |
| SEL-07: no move or resize on engine layouts | Allowed through position overrides |

---

## Sources

- RustPython source at `123dece` (2026-11-02 JST), README ("CPython >= 3.15.0"), `wasm/README.md`, `crates/capi`, `crates/wasm` [V].
- npm `rustpython_wasm`: latest `0.1.0-pre-alpha.2`, last modified 2022-05-16 [V].
- [Rust for CPython, Language Summit 2026](https://blog.python.org/2026/09/language-summit-2026-rust-for-cpython/): RustPython is not as fast as CPython.
- [rustpython-vm on lib.rs](https://lib.rs/crates/rustpython-vm): 0.6.0 released 2026-10-02.
- [Pydantic: Emscripten wheels](https://pydantic.dev/articles/emscripten-wheels-pydantic): maturin-action with a pinned emsdk per Pyodide platform.
- [Simon Willison, PyO3 on Pyodide (2026-02)](https://simonwillison.net/2026/Feb/6/pyo3-pyodide-wasm/): nightly Rust and `-Z emscripten-wasm-eh`.
- [PEP 783 discussion](https://discuss.python.org/t/pep-783-emscripten-packaging/86862): abi3 on Emscripten.

---

## 8. Decision (2026-11-01, user)

The user changed the premise, so sections 1–6 are now background:

- **The canvas edits YAML only.** Python specs convert one way with `yaml_io.dump` (`yaml_io.py:395`, the
  coordinate-complete form `spinagram layout` already uses). Python stays supported in the code editor and preview.
  No user Python runs in the browser, so **RustPython and Pyodide are dropped**, along with Python write-back and
  the override sidecar.
- **The browser engine is the Rust core**, grown from its leaves (text, route, CSS, SVG, PNG) to the whole
  YAML → scene pipeline and compiled with wasm-bindgen. The first milestone covers **hand-placed** diagrams, which
  is all the canvas produces. Autolayout follows.
- **Targets:** local `serve` (the server render stays as fallback) and a static web playground (where dot and d2
  are unavailable).
- **Edit operations live in Rust**, together with the YAML patch that keeps comments, and are shared by the
  canvas, MCP, the CLI and Python.
- **Render path:** scene diffs keyed by element id. React updates only the SVG elements that changed.
- **First features:**
  - live reflow and smart edges while dragging;
  - code↔canvas sync and live QA;
  - AI edits through the same operations, shown as a ghost preview.
- **Code size:** the server loses its render, styles and theme-preview endpoints (about 400–600 of its 1,333
  lines) [A]. The frontend stays about the same size while gaining features. The repository total grows until the
  Python layout delegates to Rust.

The spec is `features/wasm-editor/spec.md`. It supersedes the spike spec that this section replaced.
