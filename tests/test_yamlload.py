"""yamlload: libyaml parser choice and the stat-keyed file cache (spec YAML-01..05)."""
import os
from unittest import mock

import pytest
import yaml

from spinagram import yamlload

SAMPLE = "a: yes\nb: on\nc: ~\nd:\n  e: [1, 2.5, text]\n  f: {g: no}\n"


def test_uses_csafeloader_with_libyaml():  # YAML-01
    if not yaml.__with_libyaml__:
        pytest.skip("libyaml not available")
    with mock.patch.object(yaml, "load", wraps=yaml.load) as spy:
        yamlload.parse("a: 1")
    assert spy.call_args.kwargs["Loader"] is yaml.CSafeLoader


def test_falls_back_to_safeloader_with_same_data():  # YAML-02
    with mock.patch.object(yaml, "__with_libyaml__", False), mock.patch.object(yaml, "load", wraps=yaml.load) as spy:
        data = yamlload.parse(SAMPLE)
    assert spy.call_args.kwargs["Loader"] is yaml.SafeLoader
    assert data == yaml.safe_load(SAMPLE)
    assert data["a"] is True and data["b"] is True and data["c"] is None


def test_unchanged_file_parses_once(tmp_path):  # YAML-03
    f = tmp_path / "t.yaml"
    f.write_text("a: 1\n")
    with mock.patch.object(yamlload, "parse", wraps=yamlload.parse) as spy:
        assert yamlload.load_file(f) == {"a": 1}
        assert yamlload.load_file(f) == {"a": 1}
    assert spy.call_count == 1


def test_changed_content_and_size_reparses(tmp_path):  # YAML-04 clause 1 (size)
    f = tmp_path / "t.yaml"
    f.write_text("a: 1\n")
    assert yamlload.load_file(f) == {"a": 1}
    f.write_text("a: 1\nb: 22\n")
    assert yamlload.load_file(f) == {"a": 1, "b": 22}


def test_changed_mtime_only_reparses(tmp_path):  # YAML-04 clause 2 (mtime_ns, same size)
    f = tmp_path / "t.yaml"
    f.write_text("a: 1\n")
    st = os.stat(f)
    assert yamlload.load_file(f) == {"a": 1}
    f.write_text("a: 2\n")  # same size
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert yamlload.load_file(f) == {"a": 2}


def test_mutating_result_does_not_touch_next_load(tmp_path):  # YAML-05
    f = tmp_path / "t.yaml"
    f.write_text("a: {b: [1, 2]}\n")
    first = yamlload.load_file(f)
    first["a"]["b"].append(3)
    first["z"] = 1
    assert yamlload.load_file(f) == {"a": {"b": [1, 2]}}


def test_empty_file_returns_none(tmp_path):  # edge: same as safe_load
    f = tmp_path / "t.yaml"
    f.write_text("")
    assert yamlload.load_file(f) is None


def test_missing_file_raises_filenotfound(tmp_path):  # edge: same exception type as before
    with pytest.raises(FileNotFoundError):
        yamlload.load_file(tmp_path / "nope.yaml")
