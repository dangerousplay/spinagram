"""Live editor in ``spinagram serve``: code panel sources, safe writes and opening folders
(spec: .specs/features/live-editor/spec.md)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pytest.importorskip("starlette")

from spinagram.ui import files  # noqa: E402

SPEC = "id: A\ntitle: A\nnodes: [{id: n, title: Node}]\n"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# T1 · file helpers -----------------------------------------------------------------------------------
def test_list_dir_lists_subdirectories_with_spec_counts(tmp_path):  # DIR-02
    (tmp_path / "aws").mkdir()
    (tmp_path / "aws" / "a.py").write_text("x = 1\n")
    (tmp_path / "aws" / "b.yaml").write_text(SPEC)
    (tmp_path / "aws" / "_helper.py").write_text("")  # helpers are not specs
    (tmp_path / "aws" / "notes.md").write_text("")
    (tmp_path / "empty").mkdir()
    (tmp_path / "top.yml").write_text(SPEC)
    got = files.list_dir(tmp_path)
    assert got["path"] == str(tmp_path.resolve())
    assert got["parent"] == str(tmp_path.resolve().parent)
    assert got["specs"] == 1
    assert [(d["name"], d["specs"]) for d in got["dirs"]] == [("aws", 2), ("empty", 0)]
    assert got["dirs"][0]["path"] == str((tmp_path / "aws").resolve())


def test_list_dir_hides_hidden_and_generated_folders(tmp_path):  # DIR-07
    for name in [".git", ".venv", "venv", "node_modules", "__pycache__", "out", "dist", "build",
                 "site-packages", "specs"]:
        (tmp_path / name).mkdir()
    assert [d["name"] for d in files.list_dir(tmp_path)["dirs"]] == ["specs"]


def test_list_dir_rejects_a_file_or_missing_path(tmp_path):  # DIR-05
    (tmp_path / "f.py").write_text("")
    with pytest.raises(NotADirectoryError, match=f"not a directory: {tmp_path / 'f.py'}"):
        files.list_dir(tmp_path / "f.py")
    with pytest.raises(NotADirectoryError, match="not a directory: "):
        files.list_dir(tmp_path / "missing")


def test_list_dir_at_filesystem_root_has_no_parent():
    assert files.list_dir(Path("/"))["parent"] is None


def test_read_source_normalises_newlines_and_reports_version_and_language(tmp_path):  # SRC-01, SRC-08
    raw = b"from spinagram import Diagram\r\nd = Diagram('A', 'A')\r\n"
    (tmp_path / "a.py").write_bytes(raw)
    src = files.read_source(tmp_path / "a.py")
    assert src.text == "from spinagram import Diagram\nd = Diagram('A', 'A')\n"
    assert src.newline == "\r\n"
    assert src.version == _sha(raw)
    assert src.language == "python"
    (tmp_path / "s.css").write_bytes(b"node { fill: red }\n")
    css = files.read_source(tmp_path / "s.css")
    assert (css.language, css.newline) == ("css", "\n")
    (tmp_path / "d.yaml").write_text(SPEC)
    assert files.read_source(tmp_path / "d.yaml").language == "yaml"
    (tmp_path / "x.yml").write_text(SPEC)
    assert files.read_source(tmp_path / "x.yml").language == "yaml"


# T2 · recursive workspace, contains, open --------------------------------------------------------------
from spinagram.ui.workspace import Workspace  # noqa: E402


def _tree(root: Path) -> None:
    (root / "top.yaml").write_text(SPEC.replace("id: A", "id: TOP"))
    (root / "aws").mkdir()
    (root / "aws" / "eks.yaml").write_text(SPEC.replace("id: A", "id: EKS"))
    (root / "aws" / "deep").mkdir()
    (root / "aws" / "deep" / "x.yaml").write_text(SPEC.replace("id: A", "id: DEEP"))
    for skip in ["node_modules", ".hidden", "out"]:
        (root / skip).mkdir()
        (root / skip / "s.yaml").write_text(SPEC.replace("id: A", "id: SKIP"))


def test_directory_root_is_scanned_recursively_with_subfolder_keys(tmp_path):  # DIR-06, DIR-07, DIR-09
    _tree(tmp_path)
    ws = Workspace([tmp_path])
    assert sorted(ws.all_keys()) == ["aws/deep/x.yaml#DEEP", "aws/eks.yaml#EKS", "top.yaml#TOP"]
    assert ws.summary()["truncated"] is False


def test_scan_stops_at_the_cap_and_reports_truncation(tmp_path, monkeypatch):  # DIR-08
    _tree(tmp_path)
    monkeypatch.setattr(files, "MAX_SPECS", 2)
    ws = Workspace([tmp_path])
    # scan order: names sorted, a folder's files before its subfolders → top.yaml, aws/eks.yaml, aws/deep/x.yaml
    assert sorted(ws.all_keys()) == ["aws/eks.yaml#EKS", "top.yaml#TOP"]
    assert ws.summary()["truncated"] is True


def test_contains_follows_roots_and_skip_list(tmp_path):  # DIR-04
    _tree(tmp_path)
    ws = Workspace([tmp_path])
    assert ws.contains(tmp_path / "aws" / "deep" / "x.yaml")
    assert not ws.contains(tmp_path / "node_modules" / "s.yaml")
    assert not ws.contains(tmp_path / ".hidden" / "s.yaml")
    assert not ws.contains(tmp_path.parent / "elsewhere.yaml")
    single = Workspace([tmp_path / "top.yaml"])
    assert single.contains(tmp_path / "top.yaml") and not single.contains(tmp_path / "aws" / "eks.yaml")


def test_open_swaps_the_root(tmp_path):  # DIR-03
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "a.yaml").write_text(SPEC.replace("id: A", "id: ONE"))
    (tmp_path / "two").mkdir()
    (tmp_path / "two" / "sub").mkdir()
    (tmp_path / "two" / "sub" / "b.yaml").write_text(SPEC.replace("id: A", "id: TWO"))
    ws = Workspace([tmp_path / "one"])
    ws.open(tmp_path / "two")
    assert ws.all_keys() == ["sub/b.yaml#TWO"]
    assert ws.summary()["paths"] == [str((tmp_path / "two").resolve())]
    svg, _ = ws.render("sub/b.yaml#TWO")
    assert "Node" in svg


def test_open_a_non_directory_keeps_the_workspace(tmp_path):  # DIR-05
    (tmp_path / "a.yaml").write_text(SPEC)
    ws = Workspace([tmp_path])
    with pytest.raises(NotADirectoryError, match=f"not a directory: {tmp_path / 'nope'}"):
        ws.open(tmp_path / "nope")
    assert ws.all_keys() == ["a.yaml#A"] and ws.summary()["paths"] == [str(tmp_path.resolve())]


# T3 · source listing --------------------------------------------------------------------------------
def _styled(root: Path, shared: Path) -> None:
    (root / "_defaults.yaml").write_text("stylesheets: [team.css]\n")
    (root / "team.css").write_text("node { fill: #EEEEEE }\n")
    (root / "own.css").write_text("node { stroke: #111111 }\n")
    shared.write_text("edge { stroke: #222222 }\n")
    (root / "a.py").write_text(
        "from spinagram import Diagram\n"
        "d = Diagram('A', 'A')\n"
        "d.stylesheet('own.css')\n"
        f"d.stylesheet({str(shared)!r})\n"
        "d.stylesheet('node { opacity: 0.9 }')\n"   # CSS text, not a file
        "d.stylesheet('gone.css')\n"                # missing file
        "d.stylesheet('own.css')\n"                 # listed once
        "d.box('Node')\n")


def test_source_lists_spec_then_cascade_stylesheet_files(tmp_path):  # SRC-01, EDIT-01
    root = tmp_path / "specs"
    root.mkdir()
    shared = tmp_path / "shared.css"
    _styled(root, shared)
    ws = Workspace([root])
    got = ws.source("a.py#A")
    assert [f["path"] for f in got] == ["a.py", "team.css", "own.css", str(shared.resolve())]
    assert [f["language"] for f in got] == ["python", "css", "css", "css"]
    assert got[0]["text"] == (root / "a.py").read_text()
    assert got[1]["version"] == _sha((root / "team.css").read_bytes())


def test_source_of_a_spec_that_fails_to_load_still_lists_the_file(tmp_path):  # EDIT-06
    (tmp_path / "bad.py").write_text("from spinagram import Diagram\nd = Diagram('B', 'B')\nraise ValueError('boom')\n")
    ws = Workspace([tmp_path])
    got = ws.source("bad.py#B")
    assert [f["path"] for f in got] == ["bad.py"] and "boom" in got[0]["text"]


def test_source_of_an_unknown_diagram_is_a_key_error(tmp_path):
    (tmp_path / "a.yaml").write_text(SPEC)
    ws = Workspace([tmp_path])
    with pytest.raises(KeyError):
        ws.source("a.yaml#NOPE")
    with pytest.raises(KeyError):
        ws.source("missing.yaml#A")


# T4 · safe write ------------------------------------------------------------------------------------
from spinagram.ui.workspace import VersionConflict  # noqa: E402


def _ws_with_sheet(tmp_path):
    root = tmp_path / "specs"
    root.mkdir()
    shared = tmp_path / "shared.css"
    _styled(root, shared)
    (root / "_helper.py").write_text("X = 1\n")
    return Workspace([root]), root, shared


def test_write_saves_text_and_returns_the_new_version(tmp_path):  # SRC-02
    ws, root, shared = _ws_with_sheet(tmp_path)
    old = ws.source("a.py#A")[2]  # own.css
    new = ws.write("own.css", "node { stroke: #ABCDEF }\n", old["version"])
    assert (root / "own.css").read_bytes() == b"node { stroke: #ABCDEF }\n"
    assert new == _sha(b"node { stroke: #ABCDEF }\n")
    ws.write(str(shared.resolve()), "edge { stroke: red }\n", _sha(shared.read_bytes()))  # outside the root, listed
    assert shared.read_text() == "edge { stroke: red }\n"


def test_write_with_a_stale_version_is_refused(tmp_path):  # SRC-03
    ws, root, _ = _ws_with_sheet(tmp_path)
    before = (root / "own.css").read_bytes()
    with pytest.raises(VersionConflict) as err:
        ws.write("own.css", "changed\n", "0" * 64)
    assert err.value.current == _sha(before)
    assert (root / "own.css").read_bytes() == before


def test_write_to_an_unlisted_path_is_refused(tmp_path):  # SRC-04
    ws, root, _ = _ws_with_sheet(tmp_path)
    for path in ["_helper.py", "../outside.py", str(tmp_path / "elsewhere.css"), "gone.css"]:
        with pytest.raises(PermissionError, match="not an editable file"):
            ws.write(path, "x\n", "0" * 64)
    assert (root / "_helper.py").read_text() == "X = 1\n"
    assert not (tmp_path / "outside.py").exists() and not (tmp_path / "elsewhere.css").exists()


def test_write_keeps_crlf_newlines(tmp_path):  # SRC-08
    ws, root, _ = _ws_with_sheet(tmp_path)
    (root / "own.css").write_bytes(b"a {}\r\nb {}\r\n")
    ws.write("own.css", "a { fill: red }\nb {}\n", _sha(b"a {}\r\nb {}\r\n"))
    assert (root / "own.css").read_bytes() == b"a { fill: red }\r\nb {}\r\n"


def test_write_is_atomic(tmp_path, monkeypatch):  # SRC-07
    import os

    ws, root, _ = _ws_with_sheet(tmp_path)
    before = (root / "own.css").read_bytes()

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        ws.write("own.css", "half\n", _sha(before))
    assert (root / "own.css").read_bytes() == before
    assert sorted(p.name for p in root.iterdir()) == ["_defaults.yaml", "_helper.py", "a.py", "own.css", "team.css"]


# T5 · source and file routes --------------------------------------------------------------------------
from starlette.testclient import TestClient  # noqa: E402

from spinagram.ui.server import create_app  # noqa: E402

H = {"X-Spinagram": "1"}


def _client(ws: Workspace) -> TestClient:
    return TestClient(create_app(ws, watch=False), base_url="http://127.0.0.1")


def test_source_route_lists_files(tmp_path):  # SRC-01
    ws, root, shared = _ws_with_sheet(tmp_path)
    with _client(ws) as c:
        r = c.get("/api/diagrams/a.py%23A.source", headers=H)
        assert r.status_code == 200
        assert [f["path"] for f in r.json()["files"]] == ["a.py", "team.css", "own.css", str(shared.resolve())]
        assert r.headers["cache-control"] == "no-store"
        assert c.get("/api/diagrams/a.py%23NOPE.source", headers=H).status_code == 404


def test_save_route_writes_and_returns_the_version(tmp_path):  # SRC-02
    ws, root, _ = _ws_with_sheet(tmp_path)
    with _client(ws) as c:
        v = c.get("/api/diagrams/a.py%23A.source", headers=H).json()["files"][2]["version"]
        r = c.put("/api/files", headers=H, json={"path": "own.css", "text": "node { fill: red }\n", "version": v})
        assert r.status_code == 200 and r.json() == {"version": _sha(b"node { fill: red }\n")}
        assert (root / "own.css").read_text() == "node { fill: red }\n"


def test_save_route_refuses_stale_versions_with_409(tmp_path):  # SRC-03
    ws, root, _ = _ws_with_sheet(tmp_path)
    before = (root / "own.css").read_bytes()
    with _client(ws) as c:
        r = c.put("/api/files", headers=H, json={"path": "own.css", "text": "x\n", "version": "0" * 64})
        assert r.status_code == 409 and r.json()["version"] == _sha(before)
    assert (root / "own.css").read_bytes() == before


def test_save_route_refuses_unlisted_paths_with_403(tmp_path):  # SRC-04
    ws, root, _ = _ws_with_sheet(tmp_path)
    with _client(ws) as c:
        r = c.put("/api/files", headers=H, json={"path": "_helper.py", "text": "x\n", "version": "0" * 64})
        assert r.status_code == 403
    assert (root / "_helper.py").read_text() == "X = 1\n"


def test_save_route_limits_size_and_encoding(tmp_path):  # SRC-05
    ws, root, _ = _ws_with_sheet(tmp_path)
    before = (root / "own.css").read_bytes()
    with _client(ws) as c:
        big = {"path": "own.css", "text": "a" * (1024 * 1024), "version": _sha(before)}
        assert c.put("/api/files", headers=H, json=big).status_code == 413
        bad = b'{"path": "own.css", "text": "\xff", "version": "' + _sha(before).encode() + b'"}'
        assert c.put("/api/files", headers={**H, "content-type": "application/json"}, content=bad).status_code == 422
        assert c.put("/api/files", headers=H, content=b"not json").status_code == 422
        assert c.put("/api/files", headers=H, json={"path": "own.css"}).status_code == 422
    assert (root / "own.css").read_bytes() == before


def test_source_and_save_need_the_header(tmp_path):  # SRC-06
    ws, root, _ = _ws_with_sheet(tmp_path)
    before = (root / "own.css").read_bytes()
    with _client(ws) as c:
        assert c.get("/api/diagrams/a.py%23A.source").status_code == 403
        r = c.put("/api/files", json={"path": "own.css", "text": "x\n", "version": _sha(before)})
        assert r.status_code == 403 and r.json()["error"] == "missing X-Spinagram header"
        assert c.put("/api/files", headers={"X-Spinagram": "0"},
                     json={"path": "own.css", "text": "x\n", "version": _sha(before)}).status_code == 403
        assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
    assert (root / "own.css").read_bytes() == before


# T6 · folder routes, nested reloads, watcher retarget -------------------------------------------------
import time  # noqa: E402

from spinagram.ui.events import EventBus  # noqa: E402
from spinagram.ui.server import apply_changes  # noqa: E402


class Recorder(EventBus):
    def __init__(self):
        super().__init__()
        self.events: list[dict] = []

    def publish(self, event: dict) -> None:
        self.events.append(event)
        super().publish(event)


def test_fs_route_lists_the_root_and_any_folder(tmp_path):  # DIR-02
    _tree(tmp_path)
    ws = Workspace([tmp_path])
    with _client(ws) as c:
        root = c.get("/api/fs", headers=H).json()
        assert root["path"] == str(tmp_path.resolve()) and [d["name"] for d in root["dirs"]] == ["aws"]
        sub = c.get("/api/fs", headers=H, params={"path": str(tmp_path / "aws")}).json()
        assert [(d["name"], d["specs"]) for d in sub["dirs"]] == [("deep", 1)] and sub["specs"] == 1
        r = c.get("/api/fs", headers=H, params={"path": str(tmp_path / "nope")})
        assert r.status_code == 404 and r.json()["error"] == f"not a directory: {tmp_path / 'nope'}"
        assert c.get("/api/fs").status_code == 403


def test_open_route_switches_the_workspace_and_announces_it(tmp_path):  # DIR-03
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "a.yaml").write_text(SPEC.replace("id: A", "id: ONE"))
    (tmp_path / "two").mkdir()
    _tree(tmp_path / "two")
    bus = Recorder()
    ws = Workspace([tmp_path / "one"])
    with TestClient(create_app(ws, bus=bus, watch=False), base_url="http://127.0.0.1") as c:
        r = c.post("/api/workspace/open", headers=H, json={"path": str(tmp_path / "two")})
        assert r.status_code == 200
        assert r.json()["paths"] == [str((tmp_path / "two").resolve())]
        assert sorted(d["key"] for f in r.json()["files"] for d in f["diagrams"]) == [
            "aws/deep/x.yaml#DEEP", "aws/eks.yaml#EKS", "top.yaml#TOP"]
        assert {"type": "workspace"} in bus.events


def test_open_route_rejects_a_bad_path_and_keeps_the_workspace(tmp_path):  # DIR-05
    (tmp_path / "a.yaml").write_text(SPEC)
    ws = Workspace([tmp_path])
    with _client(ws) as c:
        r = c.post("/api/workspace/open", headers=H, json={"path": str(tmp_path / "a.yaml")})
        assert r.status_code == 404 and r.json()["error"] == f"not a directory: {tmp_path / 'a.yaml'}"
        assert c.post("/api/workspace/open", json={"path": str(tmp_path)}).status_code == 403
        assert c.post("/api/workspace/open", headers=H, json={}).status_code == 422
    assert ws.all_keys() == ["a.yaml#A"]


def test_saving_a_nested_spec_rerenders_it(tmp_path):  # DIR-04
    _tree(tmp_path)
    ws = Workspace([tmp_path])
    f = tmp_path / "aws" / "deep" / "x.yaml"
    f.write_text(SPEC.replace("id: A", "id: DEEP").replace("title: Node", "title: Renamed"))
    events = apply_changes(ws, ws.theme_roots(), {f.resolve()})
    assert {"type": "diagram", "keys": ["aws/deep/x.yaml#DEEP"]} in events
    assert "Renamed" in ws.render("aws/deep/x.yaml#DEEP")[0]


def test_watcher_follows_an_opened_folder(tmp_path):  # DIR-04
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "a.yaml").write_text(SPEC.replace("id: A", "id: ONE"))
    (tmp_path / "two" / "sub").mkdir(parents=True)
    target = tmp_path / "two" / "sub" / "b.yaml"
    target.write_text(SPEC.replace("id: A", "id: TWO"))
    bus = Recorder()
    ws = Workspace([tmp_path / "one"])
    with TestClient(create_app(ws, bus=bus, watch=True), base_url="http://127.0.0.1") as c:
        assert c.post("/api/workspace/open", headers=H, json={"path": str(tmp_path / "two")}).status_code == 200
        deadline = time.time() + 10
        while time.time() < deadline:
            target.write_text(SPEC.replace("id: A", "id: TWO").replace("title: Node", f"title: T{time.time()}"))
            time.sleep(0.5)
            if any(e.get("type") == "diagram" and "sub/b.yaml#TWO" in e.get("keys", []) for e in bus.events):
                break
        assert any(e.get("type") == "diagram" and "sub/b.yaml#TWO" in e.get("keys", []) for e in bus.events)


# T18 · several roots never share a display path ----------------------------------------------------------
def test_saving_with_several_roots_writes_the_named_file_only(tmp_path):  # SRC-01, SRC-04
    for name in ("one", "two"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "a.yaml").write_text(SPEC)  # identical files, same relative path
    ws = Workspace([tmp_path / "one", tmp_path / "two"])
    key = next(k for k in ws.all_keys() if k.startswith("one/"))
    spec = ws.source(key)[0]
    assert spec["path"] != next(f for k in ws.all_keys() if k.startswith("two/") for f in ws.source(k))["path"]
    ws.write(spec["path"], SPEC.replace("title: Node", "title: Saved"), spec["version"])
    assert "Saved" in (tmp_path / "one" / "a.yaml").read_text()
    assert (tmp_path / "two" / "a.yaml").read_text() == SPEC


# T19 · a broken spec keeps its stylesheet tabs ----------------------------------------------------------
def test_a_broken_spec_keeps_its_stylesheets_listed_and_writable(tmp_path):  # EDIT-06
    ws, root, shared = _ws_with_sheet(tmp_path)
    good = [f["path"] for f in ws.source("a.py#A")]
    (root / "a.py").write_text("from spinagram import Diagram\nd = Diagram('A', 'A')\nraise ValueError('typo')\n")
    apply_changes(ws, ws.theme_roots(), {(root / "a.py").resolve()})
    assert ws.files["a.py"].error
    listed = ws.source("a.py#A")
    assert [f["path"] for f in listed] == good
    own = next(f for f in listed if f["path"] == "own.css")
    ws.write("own.css", "node { fill: #123456 }\n", own["version"])
    assert (root / "own.css").read_text() == "node { fill: #123456 }\n"
