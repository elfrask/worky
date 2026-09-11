"""widget de terminal embebida para la consola --cli."""

from __future__ import annotations

import threading

from textual.message import Message
from textual.widget import Widget

from worky.tui.emulator import TerminalEmulator
from worky.tui.pty import PtySession

_KEY_BYTES: dict[str, str] = {
    "enter": "\r",
    "tab": "\t",
    "escape": "\x1b",
    "backspace": "\x7f",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "right": "\x1b[C",
    "left": "\x1b[D",
    "home": "\x1b[H",
    "end": "\x1b[F",
    "delete": "\x1b[3~",
    "insert": "\x1b[2~",
    "pageup": "\x1b[5~",
    "pagedown": "\x1b[6~",
    "space": " ",
}


def key_to_text(key: str, character: str | None = None) -> str | None:
    if key in _KEY_BYTES:
        return _KEY_BYTES[key]
    if key.startswith("ctrl+"):
        letter = key[5:]
        if len(letter) == 1 and "a" <= letter <= "z":
            return chr(ord(letter) - 96)
        return None
    if character:
        return character
    if len(key) == 1:
        return key
    return None


class TerminalView(Widget):
    can_focus = True
    DEFAULT_CSS = """
    TerminalView {
        width: 1fr;
        height: 1fr;
        background: #1c1c1c;
        color: #cccccc;
    }
    """

    class Output(Message):
        def __init__(self, data: bytes):
            self.data = data
            super().__init__()

    class Exited(Message):
        pass

    def __init__(self, session: PtySession, emulator: TerminalEmulator):
        super().__init__()
        self.session = session
        self.emulator = emulator
        self._thread: threading.Thread | None = None
        self._running = False
        self._closed = False

    def on_mount(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        self.focus()

    def on_unmount(self) -> None:
        self._running = False
        self._close()

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.session.terminate()
        except Exception:
            pass

    def _reader(self) -> None:
        while self._running:
            try:
                data = self.session.read(65536)
            except Exception:
                data = b""
            if not data:
                if not self.session.isalive():
                    break
                continue
            self.post_message(self.Output(data))
        self.post_message(self.Exited())

    def on_terminal_view_output(self, message: "TerminalView.Output") -> None:
        self.emulator.feed(message.data)
        self.refresh()

    def on_terminal_view_exited(self, message: "TerminalView.Exited") -> None:
        self.refresh()

    def on_key(self, event) -> None:
        text = key_to_text(event.key, getattr(event, "character", None))
        if text is None:
            return
        self.session.write(text)
        event.stop()
        event.prevent_default()

    def on_paste(self, event) -> None:
        self.session.write(event.text)
        event.stop()
        event.prevent_default()

    def on_resize(self, event) -> None:
        self.emulator.resize(event.size.width, event.size.height)
        self.session.resize(event.size.width, event.size.height)

    def render(self):
        return self.emulator.render()
