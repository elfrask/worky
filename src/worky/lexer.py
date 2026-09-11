"""analizador lexico del lenguaje .worky."""

from __future__ import annotations

from dataclasses import dataclass

from worky.errors import WorkyError


@dataclass
class Token:
    kind: str
    value: str
    start: int
    end: int
    line: int


OPS = set("{}[]()=,+-*/:")


class Lexer:
    def __init__(self, src: str):
        self.src = src
        self.n = len(src)
        self.i = 0
        self.line = 1

    def tokens(self) -> list[Token]:
        out: list[Token] = []
        while self.i < self.n:
            c = self.src[self.i]
            if c in " \t\r":
                self.i += 1
                continue
            if c == "\n":
                out.append(Token("NEWLINE", "\n", self.i, self.i + 1, self.line))
                self.i += 1
                self.line += 1
                continue
            if c == "/" and self.i + 1 < self.n and self.src[self.i + 1] == "/":
                while self.i < self.n and self.src[self.i] != "\n":
                    self.i += 1
                continue
            if c == '"':
                out.append(self._string())
                continue
            if c.isdigit():
                out.append(self._number())
                continue
            if c == "$":
                out.append(self._var())
                continue
            if c.isalpha() or c == "_":
                out.append(self._ident())
                continue
            if self.src.startswith("...", self.i):
                out.append(Token("SPREAD", "...", self.i, self.i + 3, self.line))
                self.i += 3
                continue
            if c in OPS:
                out.append(Token("OP", c, self.i, self.i + 1, self.line))
                self.i += 1
                continue
            out.append(Token("OP", c, self.i, self.i + 1, self.line))
            self.i += 1
        out.append(Token("EOF", "", self.n, self.n, self.line))
        return out

    def _string(self) -> Token:
        start = self.i
        line = self.line
        self.i += 1
        buf: list[str] = []
        while self.i < self.n:
            c = self.src[self.i]
            if c == "\\" and self.i + 1 < self.n:
                buf.append(c)
                buf.append(self.src[self.i + 1])
                if self.src[self.i + 1] == "\n":
                    self.line += 1
                self.i += 2
                continue
            if c == '"':
                self.i += 1
                return Token("STRING", "".join(buf), start, self.i, line)
            if c == "\n":
                self.line += 1
            buf.append(c)
            self.i += 1
        raise WorkyError(f"cadena sin cerrar en la linea {line}")

    def _number(self) -> Token:
        start = self.i
        while self.i < self.n and self.src[self.i].isdigit():
            self.i += 1
        if (
            self.i < self.n
            and self.src[self.i] == "."
            and self.i + 1 < self.n
            and self.src[self.i + 1].isdigit()
        ):
            self.i += 1
            while self.i < self.n and self.src[self.i].isdigit():
                self.i += 1
        return Token("NUMBER", self.src[start:self.i], start, self.i, self.line)

    def _var(self) -> Token:
        start = self.i
        self.i += 1
        if self.i < self.n and self.src[self.i] == "*":
            self.i += 1
            return Token("VAR", "*", start, self.i, self.line)
        if self.i < self.n and self.src[self.i] == "~":
            self.i += 1
            j = self.i
            while self.i < self.n and self.src[self.i].isdigit():
                self.i += 1
            return Token("VAR", "~" + self.src[j:self.i], start, self.i, self.line)
        j = self.i
        while self.i < self.n and (self.src[self.i].isalnum() or self.src[self.i] == "_"):
            self.i += 1
        return Token("VAR", self.src[j:self.i], start, self.i, self.line)

    def _ident(self) -> Token:
        start = self.i
        while self.i < self.n and (self.src[self.i].isalnum() or self.src[self.i] == "_"):
            self.i += 1
        return Token("IDENT", self.src[start:self.i], start, self.i, self.line)
