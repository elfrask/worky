"""interfaz de linea de comandos de worky."""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

from worky.deployers import deploy, inside_wt
from worky.errors import WorkyError
from worky.interpreter import Interpreter
from worky.kill import kill_processes
from worky.parser import Parser
from worky.platforms import PLATFORM, sanitize
from worky.render import render_script


def _configure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def find_default_file() -> str:
    if os.path.exists("workspace.worky"):
        return "workspace.worky"
    here = sorted(Path(".").glob("*.worky"))
    if here:
        return str(here[0])
    raise WorkyError("no se encontro ningun archivo .worky en el directorio actual")


def _handle_kill(argv: list[str]) -> int:
    runid = None
    if "--run" in argv:
        runid = argv[argv.index("--run") + 1]
    if "--kill-all" in argv:
        pattern = runid or "worky_"
    else:
        idx = argv.index("--kill")
        target = argv[idx + 1] if idx + 1 < len(argv) else "all"
        pattern = f"worky_{sanitize(target)}"
    kill_processes(pattern)
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    _configure_streams()
    if "--kill" in argv or "--kill-all" in argv:
        return _handle_kill(argv)

    file_path = None
    script_args: list[str] = []
    layout = "auto"
    display = "tabs-here"
    dry = False
    dump = False
    cli_mode = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--layout":
            i += 1
            layout = argv[i] if i < len(argv) else "auto"
        elif a == "--one-window":
            display = "one-window"
        elif a == "--tabs-here":
            display = "tabs-here"
        elif a == "--tabs":
            display = "tabs"
        elif a == "--windows":
            display = "windows"
        elif a == "--cli":
            cli_mode = True
        elif a == "--dry-run":
            dry = True
        elif a == "--dump":
            dump = True
        elif a in ("-h", "--help"):
            print_help()
            return 0
        elif file_path is None and (a.endswith(".worky") or os.path.exists(a)):
            file_path = a
        else:
            script_args.append(a)
        i += 1

    if cli_mode:
        from worky.tui import run_cli

        run_cli(file_path)
        return 0

    if file_path is None:
        file_path = find_default_file()

    src = Path(file_path).read_text(encoding="utf-8")
    body = Parser(src).parse()
    base_dir = os.path.dirname(os.path.abspath(file_path))

    interp = Interpreter(base_dir, script_args, create_dirs=not dry)
    interp.run(body, base_dir)

    if not interp.instances:
        print("worky: no hay instancias que desplegar")
        return 0

    runid = "wk" + uuid.uuid4().hex[:8]
    run_dir = os.path.join(tempfile.gettempdir(), "worky", runid)
    os.makedirs(run_dir, exist_ok=True)

    rendered = [render_script(inst, runid, run_dir, interp.eval) for inst in interp.instances]

    print(f"worky: {len(interp.instances)} instancia(s) [{PLATFORM}] {display} -> {runid}")
    for r in rendered:
        print(f"  - {r.instance.name}  @  {r.instance.cwd}")
        if dump:
            print("    " + r.body.replace("\n", "\n    ").rstrip())

    lines = deploy(rendered, display, layout, dry)
    if PLATFORM == "win32" and display == "tabs-here" and not inside_wt() and not dry:
        print("worky: no se detecto Windows Terminal; se abrio una ventana nueva")
    if dry:
        for line in lines:
            print(line)
    return 0


def print_help() -> None:
    print(
        "uso: worky [archivo.worky] [opciones] [-- args...]\n"
        "\n"
        "presentacion:\n"
        "  --tabs-here      pestanas en la ventana de Windows Terminal actual (por defecto)\n"
        "  --windows        ventanas separadas auto-organizadas\n"
        "  --one-window     todos en una ventana con paneles acoplados\n"
        "  --tabs           una ventana nueva con una pestana por instancia\n"
        "\n"
        "consola interactiva:\n"
        "  --cli [archivo]  consola avanzada con pestanas y terminales embebidas\n"
        "                   (Ctrl+P abre la paleta; permite fork, nuevas instancias,\n"
        "                    configuracion en caliente y guardar el workspace en .worky)\n"
        "\n"
        "opciones:\n"
        "  --layout auto|columns|rows|grid   disposicion (auto por defecto)\n"
        "  --dry-run                         muestra que se ejecutaria sin desplegar\n"
        "  --dump                            muestra los scripts generados\n"
        "\n"
        "control:\n"
        "  worky --kill <nombre> --run <id>\n"
        "  worky --kill-all --run <id>\n"
    )
