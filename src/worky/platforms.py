"""deteccion de plataforma y utilidades de formato."""

from __future__ import annotations

import re
import sys
from typing import Any


def detect_platform() -> str:
    if sys.platform.startswith("win"):
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


PLATFORM = detect_platform()


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def fmt_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list):
        return " ".join(fmt_value(v) for v in value)
    return str(value)
