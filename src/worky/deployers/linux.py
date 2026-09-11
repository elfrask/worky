"""despliegue de instancias en emuladores de terminal de Linux."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess

from worky.errors import WorkyError
from worky.render import Rendered


def _find_terminal() -> str:
    term = os.environ.get("TERMINAL")
    candidates = [term] if term else []
    candidates += [
        "x-terminal-emulator",
        "gnome-terminal",
        "konsole",
        "xfce4-terminal",
        "alacritty",
        "kitty",
        "xterm",
    ]
    chosen = next((c for c in candidates if c and shutil.which(c)), None)
    if chosen is None:
        raise WorkyError("no se encontro un emulador de terminal para desplegar")
    return chosen


def deploy_linux(rendered: list[Rendered], layout: str, dry: bool) -> list[str]:
    chosen = _find_terminal()
    launched: list[str] = []
    for r in rendered:
        script = f"cd {shlex.quote(r.instance.cwd)} && exec bash {shlex.quote(r.script_path)}"
        if "gnome-terminal" in chosen:
            cmd = [chosen, "--title", f"{r.instance.name}", "--", "bash", "-c", script]
        else:
            cmd = [chosen, "-e", "bash", "-c", script]
        launched.append(" ".join(shlex.quote(c) for c in cmd))
        if not dry:
            subprocess.Popen(cmd, close_fds=True)
    return launched
