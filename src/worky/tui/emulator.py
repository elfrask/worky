"""emulacion de pantalla de terminal con pyte."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

_BASE_COLORS = {
    "black": "#1c1c1c",
    "red": "#c50f1f",
    "green": "#13a10e",
    "brown": "#c19c00",
    "blue": "#0037da",
    "magenta": "#881798",
    "cyan": "#3a96dd",
    "white": "#cccccc",
    "brightblack": "#767676",
    "brightred": "#e74856",
    "brightgreen": "#16c60c",
    "brightyellow": "#f9f1a5",
    "brightblue": "#3b78ff",
    "brightmagenta": "#b4009e",
    "brightcyan": "#61d6d6",
    "brightwhite": "#f2f2f2",
}


def _color(value: str | None) -> str | None:
    if not value or value == "default":
        return None
    if len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value):
        return "#" + value
    return _BASE_COLORS.get(value)


class TerminalEmulator:
    def __init__(self, cols: int = 80, rows: int = 24):
        import pyte

        self.cols = cols
        self.rows = rows
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)
        self._style_cache: dict[tuple, Style] = {}

    def feed(self, data: bytes) -> None:
        try:
            self.stream.feed(data)
        except Exception:
            pass

    def resize(self, cols: int, rows: int) -> None:
        if cols == self.cols and rows == self.rows:
            return
        self.cols = max(cols, 1)
        self.rows = max(rows, 1)
        try:
            self.screen.resize(self.rows, self.cols)
        except Exception:
            pass

    def _style(self, char, fg, bg) -> Style:
        key = (fg, bg, char.bold, char.italics, char.underscore, char.strikethrough)
        cached = self._style_cache.get(key)
        if cached is not None:
            return cached
        style = Style(
            color=fg,
            bgcolor=bg,
            bold=char.bold or None,
            italic=char.italics or None,
            underline=char.underscore or None,
            strike=char.strikethrough or None,
        )
        self._style_cache[key] = style
        return style

    def render(self) -> Text:
        screen = self.screen
        text = Text()
        cursor = screen.cursor
        cursor_visible = not getattr(cursor, "hidden", False)
        cursor_key = (cursor.x, cursor.y, cursor_visible)
        for y in range(screen.lines):
            row = screen.buffer[y]
            for x in range(screen.columns):
                char = row[x]
                ch = char.data or " "
                fg = _color(char.fg)
                bg = _color(char.bg)
                if char.reverse:
                    fg, bg = bg or "#cccccc", fg or "#1c1c1c"
                style = self._style(char, fg, bg)
                if cursor_visible and x == cursor_key[0] and y == cursor_key[1]:
                    style = style + Style(reverse=True)
                text.append(ch, style=style)
            if y != screen.lines - 1:
                text.append("\n")
        return text
