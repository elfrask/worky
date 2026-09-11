"""estado de ejecucion compartido (comando con el que re-invocar worky)."""

from __future__ import annotations

import sys

_launcher: list[str] = [sys.executable, "-m", "worky"]


def set_launcher(argv: list[str]) -> None:
    """define como re-invocar worky desde los scripts generados."""
    global _launcher
    _launcher = list(argv)


def launcher() -> list[str]:
    return list(_launcher)
