# Feature: Live editor in `spinagram serve`

**Status:** Specified (2026-10-17) · **Size:** Large · **Owner:** spinagram

## Problem Statement

`spinagram serve` shows a diagram but not the code that draws it. To change a box, a user switches to an
editor, finds the spec and its stylesheet, edits, saves and switches back. The docs now lead with Python and
CSS, so the UI should put the code next to the picture and let the user edit it there. Today `serve` also
only sees the paths given on the command line, top level only, so opening another folder of diagrams (or a
tree like `examples/`) means restarting the server.

## Goals

- [ ] The diagram view shows the Python (or YAML) source of the selected diagram and every stylesheet file in
      its cascade, editable, and saving re-renders the diagram in ≤ 1 s for a typical spec.
- [ ] A user can open any local folder from the UI and see all diagrams under it, subfolders included,
      without restarting `serve`.
- [ ] No file outside the opened folder (and the stylesheets its diagrams reference) can be written from the
      UI, and no other website can read or write files through the server.

## Out of Scope

| Feature | Reason |
|---|---|
| Re-rendering from the unsaved buffer while typing | Not chosen: saving is the render trigger; runs user Python only on save |
| Creating, renaming or deleting files from the UI | Not requested; the folder's own editor/terminal does that |
| Editing helper modules (`_shapes.py`) and theme files | Not requested; only the spec and its stylesheet files are shown |
| Autocomplete, linting, formatting in the editor | Editor is syntax highlighting + editing; QA stays in `spinagram check` |
| Multi-user editing, auth, non-loopback binding | Single local user; server stays on 127.0.0.1 |
| Git integration (diff, commit) | Out of the tool's scope |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| Edit or view | Edit and save; Ctrl/Cmd+S and a Save button write the file | User choice | y |
| How to open a folder | Folder browser dialog listing subdirectories from the server, plus a path box to paste a path | User choice | y |
| Subfolders | Scanned recursively, skipping hidden folders and `node_modules`, `__pycache__`, `.venv`, `venv`, `out`, `dist`, `build`, `site-packages` | User choice; skip list avoids huge or generated trees | y |
| Scan bound | At most 2,000 spec files per opened folder; beyond that the first 2,000 by path are loaded and the workspace reports `truncated: true` | Keeps a mistaken open of `~` from hanging the server | n |
| Which files the editor shows | The spec file of the diagram, then each stylesheet file of its cascade (diagram `stylesheets` and folder `_defaults.yaml` stylesheets), in cascade order; CSS text given inline is not a file and is not shown | Matches "show the python and css code"; theme stylesheets and helpers are out of scope | n |
| Editor component | CodeMirror 6 with Python, CSS and YAML modes, loaded lazily so the catalog pages do not pay for it | Small, modular, MIT; Monaco is several MB | n |
| Conflict detection | Every read returns a `version` (SHA-256 of the bytes); a save sends it back and is refused with 409 when the file changed since | Simple, no clocks; works across editors | n |
| Write safety | Write to a temp file in the same folder, then atomic rename; keep the file's existing newline style; reject bodies > 1 MiB and non-UTF-8 text | No half-written specs; specs are small text | n |
| Writable files | Only files the editor lists for a loaded diagram (spec files under an opened root, and stylesheet files those diagrams reference) | A path parameter can never name an arbitrary file | n |
| Cross-site protection | Mutating and source-reading endpoints require header `X-Spinagram: 1` and JSON bodies; the server sends no CORS headers, so a browser page from another origin cannot send them (preflight fails) | Host check already stops DNS rebinding; this stops CSRF and cross-origin reads | n |
| Trust | Opening a folder runs its Python specs, exactly like `spinagram serve <folder>`; the dialog says so | Same trust model as the CLI; no sandbox in scope | n |
| Folder browser reach | Lists directories anywhere the user can read, starting at the current root; hidden folders are hidden unless the path box names them | Local tool, single user; user asked to point at any dir | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: See and edit the code of a diagram ⭐ MVP

**User Story**: As a diagram author, I want the Python and CSS of the diagram I am looking at next to it, and
to edit and save them there, so that I change the picture without leaving the browser.

**Why P1**: It is the feature; the docs already lead with Python and CSS.

**Acceptance Criteria**:

1. WHEN the user opens a diagram THEN the system SHALL show a code panel whose first tab is the diagram's spec file and whose further tabs are the stylesheet files of its cascade, in cascade order  <!-- event-driven -->
2. The system SHALL highlight `.py` tabs as Python, `.css` tabs as CSS and `.yaml`/`.yml` tabs as YAML  <!-- ubiquitous -->
3. WHEN the user edits a tab THEN the system SHALL mark that tab as modified until it is saved or reverted  <!-- event-driven -->
4. WHEN the user presses Ctrl+S or Cmd+S, or clicks Save, THEN the system SHALL write the tab's text to its file and clear the modified mark  <!-- event-driven -->
5. WHEN a saved file is a spec or a stylesheet of the shown diagram THEN the system SHALL re-render the diagram within 1 s for a spec of up to 50 nodes  <!-- event-driven -->
6. IF the saved spec fails to load THEN the system SHALL keep the editor text, show the error over the last good render and name the file and line when the error carries one  <!-- unwanted-behavior -->
7. WHEN a shown file changes on disk and its tab is not modified THEN the system SHALL replace the tab's text with the new content  <!-- event-driven -->
8. IF a shown file changes on disk while its tab is modified THEN the system SHALL keep the user's text and show a conflict notice with "Reload from disk" and "Keep mine" actions  <!-- unwanted-behavior -->
9. IF a save is refused because the file changed since it was read THEN the system SHALL leave the file untouched and show the conflict notice  <!-- unwanted-behavior -->
10. WHILE a tab is modified the system SHALL ask for confirmation before the user switches to another diagram or reloads the page  <!-- state-driven -->

**Independent Test**: `spinagram serve examples/tutorial/`, open step 5, change `"Shoppers"` to `"Buyers"` in
the Python tab, press Cmd+S: the file on disk changes and the diagram shows "Buyers"; change a colour in the
`checkout.css` tab, save: the colour changes.

---

### P1: Source and save API with safe writes ⭐ MVP

**User Story**: As the UI, I need to read and write a diagram's files through the server, safely, so that the
editor works without exposing the file system.

**Why P1**: The editor cannot work without it, and writing files is the riskiest part.

**Acceptance Criteria**:

1. WHEN `GET /api/diagrams/<key>.source` is called THEN the system SHALL return the list of the diagram's files (spec first, then cascade stylesheet files), each with its path relative to the open root (absolute when outside it), language, text and version  <!-- event-driven -->
2. WHEN `PUT /api/files` is called with a listed path, the text and the version that was read THEN the system SHALL write the text and return the new version  <!-- event-driven -->
3. IF the version sent differs from the file's current version THEN the system SHALL return 409 with the current version and leave the file unchanged  <!-- unwanted-behavior -->
4. IF the path is not a file listed by a loaded diagram's source THEN the system SHALL return 403 and write nothing  <!-- unwanted-behavior -->
5. IF the body is larger than 1 MiB or the text is not valid UTF-8 THEN the system SHALL return 413 or 422 respectively and write nothing  <!-- unwanted-behavior -->
6. IF a source or write request lacks the header `X-Spinagram: 1` THEN the system SHALL return 403  <!-- unwanted-behavior -->
7. The system SHALL write by creating a temporary file in the target's folder and renaming it over the target, so the target is never partly written  <!-- ubiquitous -->
8. The system SHALL keep the newline style (LF or CRLF) the file had before the save  <!-- ubiquitous -->

**Independent Test**: API tests with a temp folder: read, write, stale version → 409, path outside → 403,
missing header → 403, CRLF file keeps CRLF.

---

### P1: Open a folder of diagrams from the UI ⭐ MVP

**User Story**: As a user, I want to open another folder of diagrams from the UI, subfolders included, so that
I can browse and edit any project without restarting `serve`.

**Why P1**: Asked for explicitly; pairs with the editor.

**Acceptance Criteria**:

1. WHEN the user clicks "Open folder" THEN the system SHALL show a dialog listing the subdirectories of the current root, a parent entry, and a path box  <!-- event-driven -->
2. WHEN the user navigates into a directory in the dialog THEN the system SHALL list that directory's subdirectories and the number of spec files directly in it  <!-- event-driven -->
3. WHEN the user confirms a directory (or a path typed in the path box) THEN the system SHALL make it the workspace root, load every spec under it, and show its diagrams within the existing catalog  <!-- event-driven -->
4. WHEN a folder is opened THEN the system SHALL watch it and its subfolders so saving any spec under it re-renders the affected diagrams  <!-- event-driven -->
5. IF the typed path does not exist or is not a directory THEN the system SHALL keep the current workspace and show "not a directory: <path>"  <!-- unwanted-behavior -->
6. The system SHALL show the diagrams of a subfolder under that subfolder's relative path (for example `kubernetes/eks_platform.py`)  <!-- ubiquitous -->
7. The system SHALL skip hidden directories and `node_modules`, `__pycache__`, `.venv`, `venv`, `out`, `dist`, `build`, `site-packages` while scanning  <!-- ubiquitous -->
8. IF a folder holds more than 2,000 spec files THEN the system SHALL load the first 2,000 by path and report the workspace as truncated in the UI  <!-- unwanted-behavior -->
9. WHEN `serve` is started with a directory THEN the system SHALL scan it recursively under the same rules  <!-- event-driven -->
10. The system SHALL state in the dialog that opening a folder runs its Python specs  <!-- ubiquitous -->

**Independent Test**: start `spinagram serve examples/tutorial/`, open folder `examples/`, see
`kubernetes/eks_platform.py` and `showcase/aws_three_tier.py` in the catalog, edit one, it re-renders.

---

### P2: Jump from the diagram to the code

**User Story**: As an author, I want clicking a box in the diagram to show where it is defined, so that I find
the line to edit in a large spec.

**Why P2**: Big productivity gain on large specs, but the editor is usable without it.

**Acceptance Criteria**:

1. WHEN the user clicks a node in the diagram while the code panel is open THEN the system SHALL scroll the spec tab to the first line that contains the node's title as a string literal and select that line  <!-- event-driven -->
2. IF no line contains the title THEN the system SHALL leave the editor position unchanged  <!-- unwanted-behavior -->

**Independent Test**: open `eks_platform.py`, click "Karpenter": the editor scrolls to `karp = d.box("Karpenter", ...)`.

---

## Edge Cases

- IF two diagrams share a stylesheet THEN saving it SHALL re-render both (existing cascade mapping).
- IF the spec file is deleted while open THEN the code panel SHALL show "file removed" and disable Save.
- IF the opened folder contains no specs THEN the catalog SHALL show "no diagrams in <path>".
- WHEN a file uses CRLF newlines THEN the editor SHALL show it normally and a save SHALL keep CRLF (SRC-08).
- IF the same file is saved twice quickly THEN the second save SHALL send the version returned by the first.

---

## Implicit-requirement sweep

| Dimension | Resolution |
|---|---|
| Input validation & bounds | SRC-04, SRC-05, DIR-05, DIR-08 |
| Failure / partial-failure states | SRC-07 (atomic rename), EDIT-06 (load error keeps text) |
| Idempotency / retry / duplicates | Version check makes a retried save with a stale version a 409, never a double write (SRC-03) |
| Auth boundaries & rate limits | SRC-06 (custom header blocks cross-site), loopback bind and host check (existing); rate limits N/A because single local user |
| Concurrency / ordering | SRC-03 version check; EDIT-07/08 disk vs buffer; workspace swap holds the workspace lock while rescanning |
| Data lifecycle / expiry | N/A because files are the user's; nothing is stored by the server |
| Observability | Save and open errors returned with a message and shown in the UI; server logs at warning level as today |
| External-dependency failure | N/A because no network is involved; folder read errors surface as DIR-05 |
| State-transition integrity | EDIT-03/04/10 (modified → saved), conflict notice states (EDIT-08/09) |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| EDIT-01 | P1: code panel tabs (spec + cascade stylesheets) | Tasks | Pending |
| EDIT-02 | P1: syntax highlighting per language | Tasks | Pending |
| EDIT-03 | P1: modified mark | Tasks | Pending |
| EDIT-04 | P1: save via Ctrl/Cmd+S or button | Tasks | Pending |
| EDIT-05 | P1: re-render ≤ 1 s after save | Tasks | Pending |
| EDIT-06 | P1: load error keeps text, shows error | Tasks | Pending |
| EDIT-07 | P1: clean tab follows disk | Tasks | Pending |
| EDIT-08 | P1: dirty tab + disk change → conflict notice | Tasks | Pending |
| EDIT-09 | P1: refused save → conflict notice | Tasks | Pending |
| EDIT-10 | P1: confirm before leaving with changes | Tasks | Pending |
| SRC-01 | P1: source endpoint | Tasks | Pending |
| SRC-02 | P1: write endpoint returns new version | Tasks | Pending |
| SRC-03 | P1: stale version → 409 | Tasks | Pending |
| SRC-04 | P1: unlisted path → 403 | Tasks | Pending |
| SRC-05 | P1: > 1 MiB → 413, non-UTF-8 → 422 | Tasks | Pending |
| SRC-06 | P1: missing `X-Spinagram` header → 403 | Tasks | Pending |
| SRC-07 | P1: atomic write | Tasks | Pending |
| SRC-08 | P1: newline style kept | Tasks | Pending |
| DIR-01 | P1: open-folder dialog | Tasks | Pending |
| DIR-02 | P1: navigate directories with spec counts | Tasks | Pending |
| DIR-03 | P1: open makes it the root, loads specs | Tasks | Pending |
| DIR-04 | P1: recursive watch | Tasks | Pending |
| DIR-05 | P1: bad path keeps workspace, shows error | Tasks | Pending |
| DIR-06 | P1: subfolder-relative keys | Tasks | Pending |
| DIR-07 | P1: skip list | Tasks | Pending |
| DIR-08 | P1: 2,000-file bound, truncated flag | Tasks | Pending |
| DIR-09 | P1: CLI directory scanned recursively | Tasks | Pending |
| DIR-10 | P1: trust notice in the dialog | Tasks | Pending |
| JUMP-01 | P2: click node → spec line | Tasks | Pending |
| JUMP-02 | P2: no match → editor unchanged | Tasks | Pending |

**Coverage:** 30 total, 0 mapped to tasks, 30 unmapped ⚠️ (mapped at Tasks)

---

## Success Criteria

- [ ] Changing a title in the Python tab and saving shows the new title in ≤ 1 s on `examples/tutorial/step5_style.py`.
- [ ] Opening `examples/` from the dialog lists all 40+ example diagrams, grouped by subfolder.
- [ ] Every write-path test (403 outside, 409 stale, 403 no header, atomic write) passes.
