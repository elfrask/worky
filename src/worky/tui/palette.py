"""paleta de comandos (Ctrl+P) y dialogos de entrada de la consola --cli."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option

Action = tuple[str, str, str]


class PromptScreen(ModalScreen[str | None]):
    """pide un valor de texto y lo devuelve al cerrar."""

    BINDINGS = [("escape", "dismiss(None)", "Cancelar")]

    DEFAULT_CSS = """
    PromptScreen {
        align: center middle;
    }
    #prompt-box {
        width: 60;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    #prompt-box Label {
        margin-bottom: 1;
    }
    """

    def __init__(self, title: str, placeholder: str = ""):
        super().__init__()
        self._title = title
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-box"):
            yield Label(self._title)
            yield Input(placeholder=self._placeholder, id="prompt-input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)


class CommandPalette(ModalScreen[str | None]):
    """paleta filtrable de acciones seleccionables."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancelar"),
        Binding("up", "move(-1)", "Arriba", priority=True),
        Binding("down", "move(1)", "Abajo", priority=True),
        Binding("pageup", "move(-5)", "Arriba", priority=True),
        Binding("pagedown", "move(5)", "Abajo", priority=True),
    ]

    DEFAULT_CSS = """
    CommandPalette {
        align: center top;
    }
    #palette-box {
        width: 70;
        height: auto;
        max-height: 80%;
        margin-top: 3;
        border: round $accent;
        background: $surface;
    }
    #palette-input {
        border: none;
        border-bottom: solid $accent;
    }
    #palette-list {
        height: auto;
        max-height: 16;
        background: $surface;
    }
    """

    def __init__(self, actions: list[Action]):
        super().__init__()
        self._actions = actions
        self._filtered: list[Action] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-box"):
            yield Input(placeholder="escribe una accion y pulsa Enter...", id="palette-input")
            yield OptionList(id="palette-list")

    def on_mount(self) -> None:
        self._populate("")
        self.query_one(Input).focus()

    def _populate(self, query: str) -> None:
        option_list = self.query_one(OptionList)
        option_list.clear_options()
        self._filtered = []
        text = query.strip().lower()
        for action in self._actions:
            haystack = " ".join(action).lower()
            if text and text not in haystack:
                continue
            self._filtered.append(action)
            option_list.add_option(Option(action[1], id=action[0]))
        if self._filtered:
            option_list.highlighted = 0

    def on_input_changed(self, event: Input.Changed) -> None:
        self._populate(event.value)

    def _selected_action(self) -> Action | None:
        if not self._filtered:
            return None
        option_list = self.query_one(OptionList)
        index = option_list.highlighted
        if index is None or not (0 <= index < len(self._filtered)):
            index = 0
        return self._filtered[index]

    def action_move(self, delta: int) -> None:
        if not self._filtered:
            return
        option_list = self.query_one(OptionList)
        current = option_list.highlighted or 0
        option_list.highlighted = (current + delta) % len(self._filtered)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        action = self._selected_action()
        if action is not None:
            self.dismiss(action[0])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)
