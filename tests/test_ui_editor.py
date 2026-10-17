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
