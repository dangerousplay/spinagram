"""``requires`` on a spec: the spinagram versions it was written for (roadmap O1)."""
from __future__ import annotations

import re

_OPS = ("~=", "==", "!=", ">=", "<=", ">", "<")


def installed() -> str:
    try:
        from importlib.metadata import version

        return version("spinagram")
    except Exception:  # noqa: BLE001 - running from a source tree without metadata
        from .. import __version__

        return __version__


def _v(text: str) -> tuple[int, ...]:
    parts = [int(p) for p in re.findall(r"\d+", text)[:3]]
    return tuple(parts + [0] * (3 - len(parts)))


def satisfies(version: str, spec: str) -> bool:
    """``version`` against a comma list of clauses (``>=0.4,<0.5``, ``==0.3.*``, ``~=0.4``)."""
    v = _v(version)
    for clause in (c.strip() for c in spec.split(",") if c.strip()):
        op = next((o for o in _OPS if clause.startswith(o)), None)
        if op is None:
            raise ValueError(f"requires {spec!r}: clause {clause!r} needs one of {', '.join(_OPS)}")
        target = clause[len(op):].strip()
        if op in ("==", "!=") and target.endswith(".*"):
            pre = _v(target[:-2])[:len(re.findall(r"\d+", target))]
            ok = v[:len(pre)] == pre
            ok = ok if op == "==" else not ok
        else:
            t = _v(target)
            if op == "~=":  # compatible release: >= target and same prefix up to the last given part
                n = max(1, len(re.findall(r"\d+", target)) - 1)
                ok = v >= t and v[:n] == t[:n]
            else:
                ok = {"==": v == t, "!=": v != t, ">=": v >= t, "<=": v <= t, ">": v > t, "<": v < t}[op]
        if not ok:
            return False
    return True
