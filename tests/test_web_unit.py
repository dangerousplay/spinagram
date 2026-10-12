"""Runs the web UI's pure-logic tests (`web/src/*.test.ts`) with `bun test` when bun is installed."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "web"


@pytest.mark.skipif(shutil.which("bun") is None, reason="bun is not installed")
def test_web_unit_tests_pass():
    run = subprocess.run(["bun", "test"], cwd=WEB, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
