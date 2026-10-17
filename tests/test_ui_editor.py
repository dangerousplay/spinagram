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
