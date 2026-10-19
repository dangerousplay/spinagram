"""spinagram mcp and spinagram mcp install on the command line (spec: .specs/features/mcp-server/spec.md)."""
from __future__ import annotations

import subprocess
import sys

from spinagram import __version__


def test_python_m_spinagram_runs_the_cli():  # INST-05: the launch command agent configs use
    out = subprocess.run([sys.executable, "-m", "spinagram", "-V"], capture_output=True, text=True)
    assert out.returncode == 0
    assert out.stdout.strip() == f"spinagram {__version__}"
