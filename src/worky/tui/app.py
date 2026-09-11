"""consola interactiva de worky (worky --cli) construida con Textual."""

from __future__ import annotations

import os
from dataclasses import dataclass

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from worky.errors import WorkyError
from worky.platforms import PLATFORM
from worky.tui.emulator import TerminalEmulator
from worky.tui.palette import CommandPalette, PromptScreen
from worky.tui.pty import create_session
from worky.tui.save import render_workspace
from worky.tui.session import SessionSpec, clone_spec, shell_spec, specs_from_file
from worky.tui.widgets import TerminalView


@dataclass
class _Record:
    spec: SessionSpec
    view: TerminalView


class WorkyCliApp(App):
    TITLE = "worky --cli"
    SUB_TITLE = "Ctrl+P abre la paleta"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        background: #1c1c1c;
    }
    #tabs {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+p", "open_palette", "Paleta", priority=True),
        Binding("ctrl+t", "new_shell", "Nueva", priority=True),
        Binding("ctrl+n", "fork_session", "Fork", priority=True),
        Binding("ctrl+w", "close_session", "Cerrar", priority=True),
        Binding("ctrl+left", "prev_session", "Shell -", priority=True),
        Binding("ctrl+right", "next_session", "Shell +", priority=True),
        Binding("ctrl+q", "quit", "Salir", priority=True),
    ]

    def __init__(self, file_path: str | None = None, session_factory=None):
        super().__init__()
        self.file_path = file_path
        self._factory = session_factory or create_session
        self._records: dict[str, _Record] = {}
        self._name_counter = 0
        self._pane_counter = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield TabbedContent(id="tabs")
        yield Footer()

    def on_mount(self) -> None:
        specs: list[SessionSpec] = []
        if self.file_path:
            try:
                specs = specs_from_file(self.file_path)
            except (WorkyError, OSError) as exc:
                self.notify(f"no se pudo cargar {self.file_path}: {exc}", severity="error")
        if not specs:
            specs = [shell_spec(self._next_name("shell"), os.getcwd())]
        for spec in specs:
            self.add_session(spec, focus=False)
        self._focus_last()

    # -- gestion de sesiones ------------------------------------------------

    def _next_name(self, base: str) -> str:
        self._name_counter += 1
        return f"{base}-{self._name_counter}"

    def add_session(self, spec: SessionSpec, focus: bool = True) -> str:
        emulator = TerminalEmulator(80, 24)
        session = self._factory(spec.argv, spec.cwd)
        view = TerminalView(session, emulator)
        self._pane_counter += 1
        pane_id = f"pane-{self._pane_counter}"
        pane = TabPane(spec.name, view, id=pane_id)
        tabs = self.query_one(TabbedContent)
        tabs.add_pane(pane)
        self._records[pane_id] = _Record(spec, view)
        if focus:
            self.call_after_refresh(self._focus_pane, pane_id)
        return pane_id

    def _focus_pane(self, pane_id: str) -> None:
        tabs = self.query_one(TabbedContent)
        try:
            tabs.active = pane_id
        except Exception:
            pass
        record = self._records.get(pane_id)
        if record:
            record.view.focus()

    def _focus_last(self) -> None:
        if self._records:
            self.call_after_refresh(self._focus_pane, next(reversed(self._records)))

    def active_record(self) -> _Record | None:
        tabs = self.query_one(TabbedContent)
        pane = tabs.active_pane
        if pane is None:
            return None
        return self._records.get(pane.id)

    # -- acciones -----------------------------------------------------------

    def action_open_palette(self) -> None:
        self.push_screen(CommandPalette(self._palette_actions()), self._palette_choice)

    def action_new_shell(self) -> None:
        cwd = os.getcwd()
        record = self.active_record()
        if record:
            cwd = record.spec.cwd
        self.add_session(shell_spec(self._next_name("shell"), cwd))

    def action_fork_session(self) -> None:
        record = self.active_record()
        if record is None:
            return
        base = record.spec.name.split("-")[0] or "fork"
        self.add_session(clone_spec(record.spec, self._next_name(base)))

    def action_close_session(self) -> None:
        tabs = self.query_one(TabbedContent)
        pane = tabs.active_pane
        if pane is None:
            return
        self._records.pop(pane.id, None)
        try:
            tabs.remove_pane(pane.id)
        except Exception:
            pass

    def action_prev_session(self) -> None:
        self._cycle_session(-1)

    def action_next_session(self) -> None:
        self._cycle_session(1)

    def _cycle_session(self, delta: int) -> None:
        if not self._records:
            return
        tabs = self.query_one(TabbedContent)
        ids = list(self._records.keys())
        active = tabs.active_pane.id if tabs.active_pane else None
        index = ids.index(active) if active in ids else 0
        self._focus_pane(ids[(index + delta) % len(ids)])

    def action_quit(self) -> None:
        self.exit()

    # -- paleta -------------------------------------------------------------

    def _palette_actions(self) -> list[tuple[str, str, str]]:
        return [
            ("nueva_shell", "Nueva terminal (shell)", "abre un shell interactivo"),
            ("nueva_comando", "Nueva terminal con comando...", "abre un shell ejecutando un comando"),
            ("fork", "Fork de la terminal actual", "clona la sesion activa"),
            ("fork_comando", "Fork con comando...", "clona la sesion activa con otro comando"),
            ("cerrar", "Cerrar terminal actual", "termina la sesion activa"),
            ("renombrar", "Renombrar terminal...", "cambia el nombre de la pestana"),
            ("directorio", "Cambiar directorio...", "cd en la sesion activa"),
            ("enviar", "Escribir comando...", "enviar texto a la terminal activa"),
            ("guardar", "Guardar workspace en .worky...", "exporta las sesiones actuales"),
            ("abrir", "Abrir archivo .worky...", "carga instancias como sesiones"),
            ("salir", "Salir", "cierra worky --cli"),
        ]

    def _palette_choice(self, choice: str | None) -> None:
        if not choice:
            return
        handler = getattr(self, f"_cmd_{choice}", None)
        if handler:
            handler()

    def _prompt(self, title: str, placeholder: str, callback) -> None:
        self.push_screen(PromptScreen(title, placeholder), callback)

    def _cmd_nueva_shell(self) -> None:
        self.action_new_shell()

    def _cmd_nueva_comando(self) -> None:
        self._prompt("Comando de la nueva terminal", "pnpm run dev", self._create_with_command)

    def _cmd_fork(self) -> None:
        self.action_fork_session()

    def _cmd_fork_comando(self) -> None:
        self._prompt("Comando del fork", "pnpm run dev", self._fork_with_command)

    def _cmd_cerrar(self) -> None:
        self.action_close_session()

    def _cmd_renombrar(self) -> None:
        record = self.active_record()
        current = record.spec.name if record else ""
        self._prompt("Nuevo nombre", current, self._rename_active)

    def _cmd_directorio(self) -> None:
        record = self.active_record()
        current = record.spec.cwd if record else os.getcwd()
        self._prompt("Directorio", current, self._change_cwd)

    def _cmd_enviar(self) -> None:
        self._prompt("Texto a enviar", "git status", self._send_to_active)

    def _cmd_guardar(self) -> None:
        self._prompt("Ruta del archivo .worky", "workspace.worky", self._save_workspace)

    def _cmd_abrir(self) -> None:
        self._prompt("Archivo .worky a abrir", "workspace.worky", self._open_file)

    def _cmd_salir(self) -> None:
        self.exit()

    # -- callbacks de los prompts ------------------------------------------

    def _active_cwd(self) -> str:
        record = self.active_record()
        return record.spec.cwd if record else os.getcwd()

    def _create_with_command(self, value: str | None) -> None:
        if not value:
            return
        self.add_session(shell_spec(self._next_name("shell"), self._active_cwd(), value))

    def _fork_with_command(self, value: str | None) -> None:
        record = self.active_record()
        if record is None:
            return
        base = record.spec.name.split("-")[0] or "fork"
        name = self._next_name(base)
        if value:
            self.add_session(shell_spec(name, record.spec.cwd, value))
        else:
            self.add_session(clone_spec(record.spec, name))

    def _rename_active(self, value: str | None) -> None:
        record = self.active_record()
        if record is None or not value:
            return
        record.spec.name = value
        tabs = self.query_one(TabbedContent)
        try:
            tabs.get_tab(tabs.active_pane.id).label = value
        except Exception:
            pass

    def _change_cwd(self, value: str | None) -> None:
        record = self.active_record()
        if record is None or not value:
            return
        path = os.path.abspath(os.path.expanduser(value))
        if not os.path.isdir(path):
            self.notify(f"no existe el directorio: {path}", severity="warning")
            return
        record.spec.cwd = path
        command = f'cd /d "{path}"' if PLATFORM == "win32" else f'cd "{path}"'
        record.view.session.write(command + "\r")
        self.notify(f"cd -> {path}")

    def _send_to_active(self, value: str | None) -> None:
        record = self.active_record()
        if record is None or not value:
            return
        record.view.session.write(value + "\r")

    def _save_workspace(self, value: str | None) -> None:
        path = value or "workspace.worky"
        specs = [record.spec for record in self._records.values()]
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render_workspace(specs))
        except OSError as exc:
            self.notify(f"error al guardar: {exc}", severity="error")
            return
        self.notify(f"workspace guardado en {os.path.abspath(path)}")

    def _open_file(self, value: str | None) -> None:
        if not value:
            return
        try:
            specs = specs_from_file(value)
        except (WorkyError, OSError) as exc:
            self.notify(f"error al abrir: {exc}", severity="error")
            return
        if not specs:
            self.notify("el archivo no define instancias", severity="warning")
            return
        for spec in specs:
            self.add_session(spec, focus=False)
        self._focus_last()
