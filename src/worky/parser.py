"""analizador sintactico del lenguaje .worky."""

from __future__ import annotations

from typing import Any

from worky.errors import WorkyError
from worky.lexer import Lexer, Token
from worky.nodes import (
    ArrayLit,
    Assign,
    BinOp,
    Command,
    EnvSet,
    InBlock,
    NumLit,
    OsBlock,
    RunBlock,
    Spread,
    StrLit,
    Tool,
    VarRef,
)


class Parser:
    def __init__(self, src: str):
        self.src = src
        self.toks = Lexer(src).tokens()
        self.i = 0

    def peek(self, off: int = 0) -> Token:
        return self.toks[min(self.i + off, len(self.toks) - 1)]

    def advance(self) -> Token:
        tok = self.toks[self.i]
        if tok.kind != "EOF":
            self.i += 1
        return tok

    def at(self, kind: str, value: str | None = None) -> bool:
        tok = self.peek()
        return tok.kind == kind and (value is None or tok.value == value)

    def expect(self, kind: str, value: str | None = None) -> Token:
        if not self.at(kind, value):
            tok = self.peek()
            raise WorkyError(
                f"linea {tok.line}: se esperaba {value or kind} "
                f"pero se encontro '{tok.value or tok.kind}'"
            )
        return self.advance()

    def skip_newlines(self) -> None:
        while self.at("NEWLINE"):
            self.advance()

    def parse(self) -> list[Any]:
        body: list[Any] = []
        self.skip_newlines()
        while not self.at("EOF"):
            body.append(self.statement())
            self.skip_newlines()
        return body

    def block(self) -> list[Any]:
        self.expect("OP", "{")
        body: list[Any] = []
        self.skip_newlines()
        while not self.at("OP", "}") and not self.at("EOF"):
            body.append(self.statement())
            self.skip_newlines()
        self.expect("OP", "}")
        return body

    def statement(self) -> Any:
        tok = self.peek()
        if tok.kind == "IDENT":
            if tok.value == "in":
                return self.in_block()
            if tok.value == "run":
                return self.run_block()
            if tok.value == "os" and self.peek(1).kind == "OP" and self.peek(1).value == ":":
                return self.os_block()
            if tok.value == "set":
                return self.env_set(exported=False)
            if tok.value == "export":
                return self.env_set(exported=True)
        if tok.kind == "VAR":
            name = self.advance().value
            self.expect("OP", "=")
            return Assign(name, self.expr())
        if tok.kind == "OP" and tok.value == "/":
            return self.tool()
        return self.command()

    def in_block(self) -> InBlock:
        self.expect("IDENT", "in")
        path = self.expr()
        return InBlock(path, self.block())

    def run_block(self) -> RunBlock:
        self.expect("IDENT", "run")
        name = None
        if not self.at("OP", "{"):
            name = self.expr()
        return RunBlock(name, self.block())

    def os_block(self) -> OsBlock:
        self.expect("IDENT", "os")
        self.expect("OP", ":")
        target = self.advance().value
        return OsBlock(target, self.block())

    def env_set(self, exported: bool) -> EnvSet:
        self.advance()
        key = self.expect("IDENT").value
        self.expect("OP", "=")
        return EnvSet(key, self.expr(), exported)

    def tool(self) -> Tool:
        self.expect("OP", "/")
        name = self.advance().value
        args: list[Any] = []
        while (
            not self.at("NEWLINE")
            and not self.at("OP", "}")
            and not self.at("OP", "{")
            and not self.at("EOF")
        ):
            if self.at("STRING"):
                args.append(StrLit(self.peek().value))
                self.advance()
            elif self.at("VAR") or self.at("NUMBER") or self.at("OP", "["):
                args.append(self.expr())
            else:
                args.append(StrLit(self.advance().value))
        body = None
        if self.at("OP", "{"):
            body = self.block()
        return Tool(name, args, body)

    def command(self) -> Command:
        start_tok = self.peek()
        if start_tok.kind == "NEWLINE":
            self.advance()
            return self.command()
        start = start_tok.start
        end = start_tok.end
        while not self.at("NEWLINE") and not self.at("OP", "}") and not self.at("EOF"):
            end = self.advance().end
        text = self.src[start:end].strip()
        return Command(text)

    def expr(self) -> Any:
        return self.add()

    def add(self) -> Any:
        node = self.mul()
        while self.at("OP", "+") or self.at("OP", "-"):
            op = self.advance().value
            node = BinOp(op, node, self.mul())
        return node

    def mul(self) -> Any:
        node = self.primary()
        while self.at("OP", "*") or self.at("OP", "/"):
            op = self.advance().value
            node = BinOp(op, node, self.primary())
        return node

    def primary(self) -> Any:
        tok = self.peek()
        if tok.kind == "NUMBER":
            self.advance()
            num = float(tok.value)
            return NumLit(int(num) if num.is_integer() else num)
        if tok.kind == "STRING":
            self.advance()
            return StrLit(tok.value)
        if tok.kind == "VAR":
            self.advance()
            return VarRef(tok.value)
        if tok.kind == "SPREAD":
            self.advance()
            return Spread(self.primary())
        if tok.kind == "OP" and tok.value == "[":
            return self.array()
        if tok.kind == "OP" and tok.value == "(":
            self.advance()
            node = self.expr()
            self.expect("OP", ")")
            return node
        if tok.kind == "OP" and tok.value == "-":
            self.advance()
            return BinOp("-", NumLit(0), self.primary())
        if tok.kind == "IDENT":
            self.advance()
            return StrLit(tok.value)
        raise WorkyError(f"linea {tok.line}: expresion invalida en '{tok.value or tok.kind}'")

    def array(self) -> ArrayLit:
        self.expect("OP", "[")
        items: list[Any] = []
        while not self.at("OP", "]"):
            items.append(self.expr())
            if self.at("OP", ","):
                self.advance()
            elif not self.at("OP", "]"):
                raise WorkyError(f"linea {self.peek().line}: se esperaba ',' o ']'")
        self.expect("OP", "]")
        return ArrayLit(items)
