"""generacion de scripts a partir de las instancias interpretadas."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from typing import Any, Callable

from worky import runtime
from worky.errors import WorkyError
from worky.interpreter import Instance
from worky.nodes import Command, EnvSet, StrLit, Tool
from worky.platforms import PLATFORM, fmt_value, sanitize

EvalFn = Callable[[Any], Any]


@dataclass
class Rendered:
    instance: Instance
    script_path: str
    marker: str
    body: str


def render_script(inst: Instance, runid: str, run_dir: str, eval_fn: EvalFn) -> Rendered:
    marker_base = f"worky_{sanitize(inst.name)}"
    ext = ".cmd" if PLATFORM == "win32" else ".sh"
    marker = marker_base + ext
    script_path = os.path.join(run_dir, marker)
    lines: list[str] = []
    if PLATFORM == "win32":
        lines.append("@echo off")
        lines.append("chcp 65001 >nul")
    else:
        lines.append("#!/usr/bin/env bash")

    for action in inst.actions:
        if isinstance(action, EnvSet):
            value = fmt_value(eval_fn(action.expr))
            if PLATFORM == "win32":
                lines.append(f"set {sanitize(action.name)}={value}")
            else:
                lines.append(f"export {sanitize(action.name)}={shlex.quote(value)}")
        elif isinstance(action, Command):
            lines.append(action.text)
        elif isinstance(action, Tool):
            lines.append(render_tool(action, runid, eval_fn))

    body = "\n".join(lines) + "\n"
    with open(script_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    if PLATFORM != "win32":
        os.chmod(script_path, 0o755)
    return Rendered(inst, script_path, marker, body)


def render_tool(tool: Tool, runid: str, eval_fn: EvalFn) -> str:
    name = tool.name.lower()
    if name == "pause":
        return "pause" if PLATFORM == "win32" else 'read -r -p "Presiona Enter para continuar..." _'
    if name == "kill":
        arg = tool.args[0] if tool.args else StrLit("all")
        target = arg.raw if isinstance(arg, StrLit) else fmt_value(eval_fn(arg))
        launch = " ".join(f'"{part}"' for part in runtime.launcher())
        if target.lower() == "all":
            return f"{launch} --kill-all --run {runid}"
        quoted = f'"{target}"' if PLATFORM == "win32" else shlex.quote(target)
        return f"{launch} --kill {quoted} --run {runid}"
    if name == "shell":
        return render_shell(tool, runid, eval_fn)
    raise WorkyError(f"herramienta desconocida: /{tool.name}")


def default_shell() -> str:
    if PLATFORM == "win32":
        return "cmd"
    return os.environ.get("SHELL") or "bash"


def _arg_text(arg: Any, eval_fn: EvalFn) -> str:
    return arg.raw if isinstance(arg, StrLit) else fmt_value(eval_fn(arg))


def render_shell(tool: Tool, runid: str, eval_fn: EvalFn) -> str:
    """ejecuta el shell del sistema; con comandos los corre y deja el shell abierto."""
    commands: list[str] = []
    if tool.args:
        commands.append(" ".join(_arg_text(arg, eval_fn) for arg in tool.args))
    if tool.body is not None:
        for stmt in tool.body:
            if isinstance(stmt, Command):
                commands.append(stmt.text)
            elif isinstance(stmt, Tool):
                commands.append(render_tool(stmt, runid, eval_fn))
            elif isinstance(stmt, EnvSet):
                commands.append(f"set {sanitize(stmt.name)}={fmt_value(eval_fn(stmt.expr))}")
            else:
                raise WorkyError(
                    "solo comandos y herramientas estan permitidos dentro de /shell { ... }"
                )

    if PLATFORM == "win32":
        command = " & ".join(part for part in commands if part)
        if not command:
            return "cmd"
        return 'cmd /k "' + command.replace('"', '\\"') + '"'

    shell = default_shell()
    command = "; ".join(part for part in commands if part)
    if not command:
        return shlex.quote(shell)
    keep_open = f"{command}; exec {shlex.quote(shell)}"
    return f"{shlex.quote(shell)} -c {shlex.quote(keep_open)}"
