"""seleccion del despliegue segun la plataforma y el modo."""

from __future__ import annotations

import os

from worky.deployers import linux, windows
from worky.platforms import PLATFORM
from worky.render import Rendered

__all__ = ["deploy", "PLATFORM"]


def deploy(rendered: list[Rendered], display: str, layout: str, dry: bool) -> list[str]:
    if not rendered:
        return []
    if PLATFORM == "win32":
        if display == "one-window":
            return windows.deploy_one_window(rendered, "columns" if layout == "auto" else layout, dry)
        if display == "tabs":
            return windows.deploy_tabs(rendered, dry)
        if display == "tabs-here":
            return windows.deploy_tabs_here(rendered, dry)
        return windows.deploy_separate_windows(rendered, layout, dry)
    if display in ("one-window", "tabs-here"):
        print("worky: modo no soportado en esta plataforma; se abren ventanas separadas")
    return linux.deploy_linux(rendered, layout, dry)


def inside_wt() -> bool:
    return bool(os.environ.get("WT_SESSION"))
