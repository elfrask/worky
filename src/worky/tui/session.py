"""modelo de sesiones de la consola --cli y carga desde .worky."""

from __future__ import annotations

import os
import shlex
import tempfile
import uuid
from dataclasses import dataclass

from worky.platforms import PLATFORM
from worky.render import default_shell


@dataclass
class SessionSpec:
    name: str
    cwd: str
    argv: list[str]
    command: str | None = None
    raw: str | None = None


def shell_spec(name: str, cwd: str, command: str | None = None) -> SessionSpec:
    shell = default_shell()
    if PLATFORM == "win32":
        argv = ["cmd.exe", "/k", command] if command else ["cmd.exe"]
    else:
        argv = [shell, "-c", f"{command}; exec {shell}"] if command else [shell]
    return SessionSpec(name=name, cwd=cwd, argv=argv, command=command)


def script_spec(name: str, cwd: str, script_path: str, raw: str | None = None) -> SessionSpec:
    if PLATFORM == "win32":
        argv = ["cmd.exe", "/k", "call", script_path]
    else:
        argv = ["bash", "-c", f"source {shlex.quote(script_path)}; exec bash"]
    return SessionSpec(name=name, cwd=cwd, argv=argv, raw=raw)


def clone_spec(spec: SessionSpec, name: str) -> SessionSpec:
    return SessionSpec(
        name=name,
        cwd=spec.cwd,
        argv=list(spec.argv),
        command=spec.command,
        raw=spec.raw,
    )


def _strip_header(body: str) -> str:
    lines = body.splitlines()
    if not lines:
        return ""
    if lines[0].startswith("@echo"):
        i = 1
        while i < len(lines) and (lines[i].startswith("chcp") or not lines[i].strip()):
            i += 1
        return "\n".join(lines[i:]).strip("\n")
    if lines[0].startswith("#!"):
        return "\n".join(lines[1:]).strip("\n")
    return body.strip("\n")


def specs_from_file(path: str) -> list[SessionSpec]:
    from worky.interpreter import Interpreter
    from worky.parser import Parser
    from worky.render import render_script

    src = open(path, encoding="utf-8").read()
    body = Parser(src).parse()
    base_dir = os.path.dirname(os.path.abspath(path))
    interp = Interpreter(base_dir, [], create_dirs=False)
    interp.run(body, base_dir)

    runid = "wkc" + uuid.uuid4().hex[:6]
    run_dir = os.path.join(tempfile.gettempdir(), "worky", runid)
    os.makedirs(run_dir, exist_ok=True)

    specs: list[SessionSpec] = []
    for inst in interp.instances:
        rendered = render_script(inst, runid, run_dir, interp.eval)
        raw = _strip_header(rendered.body)
        specs.append(script_spec(inst.name, inst.cwd, rendered.script_path, raw))
    return specs
