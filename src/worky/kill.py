"""cierre de procesos de instancias desplegadas."""

from __future__ import annotations

import os
import subprocess

from worky.platforms import PLATFORM


def kill_processes(pattern: str) -> None:
    if PLATFORM == "win32":
        ps = (
            "Get-CimInstance Win32_Process | "
            f"Where-Object {{ $_.CommandLine -like '*{pattern}*' -and $_.ProcessId -ne $PID "
            f"-and $_.ProcessId -ne {os.getpid()} }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    else:
        subprocess.run(["pkill", "-f", pattern], check=False)
