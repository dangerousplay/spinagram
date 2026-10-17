"""`spinagram --version` reports the installed distribution, not a second copy of the number."""
from __future__ import annotations

from importlib.metadata import version

import pytest

import spinagram
from spinagram import cli


def test_version_comes_from_the_distribution():
    assert spinagram.__version__ == version("spinagram")


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_cli_prints_version(flag, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([flag])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"spinagram {spinagram.__version__}"
