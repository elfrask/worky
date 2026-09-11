"""despliegue de instancias en Windows Terminal."""

from __future__ import annotations

import math
import os
import subprocess

from worky.render import Rendered


def wt_pane_args(r: Rendered) -> list[str]:
    return [
        "--title", f"{r.instance.name}",
        "--suppressApplicationTitle",
        "-d", r.instance.cwd,
        "cmd.exe", "/k", "call", r.script_path,
    ]


def wt_window_args(r: Rendered) -> list[str]:
    return [
        "wt.exe", "-w", "new", "new-tab",
        "--title", f"{r.instance.name}",
        "--suppressApplicationTitle",
        "-d", r.instance.cwd,
        "cmd.exe", "/k", "call", r.script_path,
    ]


def cmd_quote(arg: str) -> str:
    if arg and not any(c in arg for c in ' \t"&^<>|'):
        return arg
    return '"' + arg.replace('"', "") + '"'


def _launch_wt(argv: list[str], dry: bool, via_start: bool = False) -> None:
    if dry:
        return
    if via_start:
        line = 'start "" ' + " ".join(cmd_quote(a) for a in argv)
        subprocess.Popen(line, shell=True)
    else:
        subprocess.Popen(argv, close_fds=True)


def grid_dims(n: int, layout: str) -> tuple[int, int]:
    if layout == "rows":
        return 1, n
    if layout == "columns":
        return n, 1
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    return cols, rows


def _enum_cascadia_windows() -> list[tuple[int, str]]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[tuple[int, str]] = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        if cls.value != "CASCADIA_HOSTING_WINDOW_CLASS":
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(proc(cb), 0)
    return found


def _wait_windows(titles: set[str], previous: set[int], timeout: float = 8.0) -> dict[str, int]:
    import time

    result: dict[str, int] = {}
    deadline = time.time() + timeout
    while time.time() < deadline:
        for hwnd, title in _enum_cascadia_windows():
            if hwnd in previous:
                continue
            if title in titles:
                result[title] = hwnd
        if len(result) >= len(titles):
            break
        time.sleep(0.25)
    return result


def _tile_windows(handles: list[int], layout: str, gap: int = 8) -> None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    work = RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)
    width = work.right - work.left
    height = work.bottom - work.top
    cols, rows = grid_dims(len(handles), layout)
    cell_w = width / cols
    cell_h = height / rows
    for i, hwnd in enumerate(handles):
        row, col = divmod(i, cols)
        x = work.left + int(col * cell_w)
        y = work.top + int(row * cell_h)
        w = int((col + 1) * cell_w) - int(col * cell_w)
        h = int((row + 1) * cell_h) - int(row * cell_h)
        user32.SetWindowPos(hwnd, 0, x, y, max(w - gap, 200), max(h - gap, 150), 0x0040)


def deploy_one_window(rendered: list[Rendered], layout: str, dry: bool) -> list[str]:
    if not rendered:
        return []
    argv: list[str] = ["wt.exe", "-w", "new"]
    n = len(rendered)
    vertical = layout != "rows"
    flag = "-V" if vertical else "-H"
    back = "left" if vertical else "up"
    argv += ["new-tab"] + wt_pane_args(rendered[0])
    m = n
    order = list(range(n - 1, 0, -1))
    for idx, inst_index in enumerate(order):
        if idx > 0:
            argv += [";", "move-focus", back]
        size = 1.0 / m
        argv += [";", "split-pane", flag, "--size", f"{size:.4f}"] + wt_pane_args(rendered[inst_index])
        m -= 1
    if not dry:
        subprocess.Popen(argv, close_fds=True)
    return [" ".join(argv)]


def deploy_tabs(rendered: list[Rendered], dry: bool) -> list[str]:
    if not rendered:
        return []
    argv: list[str] = ["wt.exe", "-w", "new", "new-tab"] + wt_pane_args(rendered[0])
    for r in rendered[1:]:
        argv += [";", "new-tab"] + wt_pane_args(r)
    if not dry:
        subprocess.Popen(argv, close_fds=True)
    return [" ".join(argv)]


def deploy_tabs_here(rendered: list[Rendered], dry: bool) -> list[str]:
    if not rendered:
        return []
    inside_wt = bool(os.environ.get("WT_SESSION"))
    window = "0" if inside_wt else "new"
    argv: list[str] = ["wt.exe", "-w", window, "new-tab"] + wt_pane_args(rendered[0])
    for r in rendered[1:]:
        argv += [";", "new-tab"] + wt_pane_args(r)
    _launch_wt(argv, dry, via_start=inside_wt)
    return [" ".join(argv)]


def deploy_separate_windows(rendered: list[Rendered], layout: str, dry: bool) -> list[str]:
    if not rendered:
        return []
    titles = {f"{r.instance.name}": r for r in rendered}
    commands = [" ".join(wt_window_args(r)) for r in rendered]
    if dry:
        cols, rows = grid_dims(len(rendered), layout)
        lines = [f"# ventanas separadas ({cols}x{rows})"]
        lines += commands
        return lines
    previous = {hwnd for hwnd, _ in _enum_cascadia_windows()}
    for r in rendered:
        subprocess.Popen(wt_window_args(r), close_fds=True)
    handles = _wait_windows(set(titles.keys()), previous)
    ordered = [handles[title] for title in titles if title in handles]
    if ordered:
        _tile_windows(ordered, layout)
    return commands
