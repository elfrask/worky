"""despliega workspaces declarativos definidos en archivos .worky."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class WorkyError(Exception):
    pass


PLATFORM = "win32" if sys.platform.startswith("win") else "linux"
if sys.platform == "darwin":
    PLATFORM = "darwin"


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def fmt_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list):
        return " ".join(fmt_value(v) for v in value)
    return str(value)


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

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
        if self.i < self.n and self.src[self.i] == "." and self.i + 1 < self.n and self.src[self.i + 1].isdigit():
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


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------

@dataclass
class NumLit:
    value: float


@dataclass
class StrLit:
    raw: str


@dataclass
class VarRef:
    name: str


@dataclass
class ArrayLit:
    items: list[Any]


@dataclass
class Spread:
    expr: Any


@dataclass
class BinOp:
    op: str
    left: Any
    right: Any


@dataclass
class Assign:
    name: str
    expr: Any


@dataclass
class EnvSet:
    name: str
    expr: Any
    exported: bool


@dataclass
class Command:
    text: str


@dataclass
class Tool:
    name: str
    args: list[Any]


@dataclass
class InBlock:
    path: Any
    body: list[Any]


@dataclass
class RunBlock:
    name: Any
    body: list[Any]


@dataclass
class OsBlock:
    target: str
    body: list[Any]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

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
                f"linea {tok.line}: se esperaba {value or kind} pero se encontro '{tok.value or tok.kind}'"
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
        while not self.at("NEWLINE") and not self.at("OP", "}") and not self.at("EOF"):
            if self.at("STRING"):
                args.append(StrLit(self.peek().value))
                self.advance()
            elif self.at("VAR") or self.at("NUMBER") or self.at("OP", "["):
                args.append(self.expr())
            else:
                args.append(StrLit(self.advance().value))
        return Tool(name, args)

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


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------

@dataclass
class Instance:
    name: str
    cwd: str
    actions: list[Any] = field(default_factory=list)


class Interpreter:
    def __init__(self, base_dir: str, script_args: list[str], create_dirs: bool = True):
        self.base_dir = base_dir
        self.args = script_args
        self.create_dirs = create_dirs
        self.vars: dict[str, Any] = {}
        self.instances: list[Instance] = []
        self._auto = 0
        self._used: set[str] = set()

    def run(self, body: list[Any], cwd: str) -> None:
        for stmt in body:
            if isinstance(stmt, Assign):
                self.vars[stmt.name] = self.eval(stmt.expr)
            elif isinstance(stmt, InBlock):
                target = fmt_value(self.eval(stmt.path))
                newdir = target if os.path.isabs(target) else os.path.normpath(os.path.join(cwd, target))
                if self.create_dirs:
                    os.makedirs(newdir, exist_ok=True)
                self.run(stmt.body, newdir)
            elif isinstance(stmt, RunBlock):
                self.instances.append(self.build_instance(stmt, cwd))
            else:
                raise WorkyError("solo 'in', 'run' y asignaciones estan permitidos en el nivel superior")

    def build_instance(self, run: RunBlock, cwd: str) -> Instance:
        if run.name is None:
            self._auto += 1
            name = f"run{self._auto}"
        else:
            name = fmt_value(self.eval(run.name))
        base = name
        counter = 2
        while name in self._used:
            name = f"{base}-{counter}"
            counter += 1
        self._used.add(name)
        actions: list[Any] = []
        for stmt in run.body:
            if isinstance(stmt, OsBlock):
                if stmt.target in (PLATFORM, "all"):
                    self.collect(stmt.body, actions)
            elif isinstance(stmt, Command):
                actions.append(stmt)
            elif isinstance(stmt, Tool):
                actions.append(stmt)
            else:
                raise WorkyError(f"contenido invalido dentro de 'run \"{name}\"'")
        return Instance(name, cwd, actions)

    def collect(self, body: list[Any], actions: list[Any]) -> None:
        for stmt in body:
            if isinstance(stmt, EnvSet):
                actions.append(stmt)
            elif isinstance(stmt, Command):
                actions.append(stmt)
            elif isinstance(stmt, Tool):
                actions.append(stmt)
            elif isinstance(stmt, OsBlock):
                if stmt.target in (PLATFORM, "all"):
                    self.collect(stmt.body, actions)
            else:
                raise WorkyError("solo comandos, 'set'/'export' y herramientas estan permitidos en bloques 'os'")

    def eval(self, node: Any) -> Any:
        if isinstance(node, NumLit):
            return node.value
        if isinstance(node, StrLit):
            return self.interpolate(node.raw)
        if isinstance(node, VarRef):
            return self.resolve(node.name)
        if isinstance(node, ArrayLit):
            out: list[Any] = []
            for item in node.items:
                if isinstance(item, Spread):
                    val = self.eval(item.expr)
                    out.extend(val if isinstance(val, list) else [val])
                else:
                    out.append(self.eval(item))
            return out
        if isinstance(node, BinOp):
            return self.binary(node)
        raise WorkyError(f"nodo desconocido: {node!r}")

    def resolve(self, name: str) -> Any:
        if name == "*":
            return list(self.args)
        if name.startswith("~"):
            idx = int(name[1:]) - 1
            return self.args[idx] if 0 <= idx < len(self.args) else ""
        if name in self.vars:
            return self.vars[name]
        raise WorkyError(f"variable no definida: ${name}")

    def binary(self, node: BinOp) -> Any:
        left = self.eval(node.left)
        right = self.eval(node.right)
        if node.op == "+" and not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
            return fmt_value(left) + fmt_value(right)
        a = float(left)
        b = float(right)
        result = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else 0}[node.op]
        return int(result) if float(result).is_integer() else result

    def interpolate(self, raw: str) -> str:
        out: list[str] = []
        i = 0
        while i < len(raw):
            c = raw[i]
            if c == "\\" and i + 1 < len(raw):
                nxt = raw[i + 1]
                out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\", "$": "$"}.get(nxt, nxt))
                i += 2
                continue
            if c == "$":
                name, j = read_var(raw, i)
                if name is None:
                    out.append(c)
                    i += 1
                    continue
                val = self.resolve(name)
                out.append(fmt_value(val))
                i = j
                continue
            out.append(c)
            i += 1
        return "".join(out)


def read_var(text: str, i: int) -> tuple[str | None, int]:
    if i + 1 >= len(text):
        return None, i
    j = i + 1
    if text[j] == "*":
        return "*", j + 1
    if text[j] == "~":
        j += 1
        k = j
        while k < len(text) and text[k].isdigit():
            k += 1
        if k == j:
            return None, i
        return "~" + text[j:k], k
    k = j
    while k < len(text) and (text[k].isalnum() or text[k] == "_"):
        k += 1
    if k == j:
        return None, i
    return text[j:k], k


# ---------------------------------------------------------------------------
# Script generation
# ---------------------------------------------------------------------------

@dataclass
class Rendered:
    instance: Instance
    script_path: str
    marker: str
    body: str


def render_script(inst: Instance, runid: str, run_dir: str, worky_path: str, eval_fn) -> Rendered:
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
            lines.append(render_tool(action, runid, worky_path, eval_fn))

    body = "\n".join(lines) + "\n"
    with open(script_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    if PLATFORM != "win32":
        os.chmod(script_path, 0o755)
    return Rendered(inst, script_path, marker, body)


def render_tool(tool: Tool, runid: str, worky_path: str, eval_fn) -> str:
    name = tool.name.lower()
    if name == "pause":
        return "pause" if PLATFORM == "win32" else 'read -r -p "Presiona Enter para continuar..." _'
    if name == "kill":
        arg = tool.args[0] if tool.args else StrLit("all")
        target = arg.raw if isinstance(arg, StrLit) else fmt_value(eval_fn(arg))
        if target.lower() == "all":
            return f'"{sys.executable}" "{worky_path}" --kill-all --run {runid}'
        quoted = f'"{target}"' if PLATFORM == "win32" else shlex.quote(target)
        return f'"{sys.executable}" "{worky_path}" --kill {quoted} --run {runid}'
    raise WorkyError(f"herramienta desconocida: /{tool.name}")


# ---------------------------------------------------------------------------
# Deployers
# ---------------------------------------------------------------------------

def _wt_pane_args(r: Rendered) -> list[str]:
    return [
        "--title", f"{r.instance.name}",
        "--suppressApplicationTitle",
        "-d", r.instance.cwd,
        "cmd.exe", "/k", "call", r.script_path,
    ]


def _wt_window_args(r: Rendered) -> list[str]:
    return [
        "wt.exe", "-w", "new", "new-tab",
        "--title", f"{r.instance.name}",
        "--suppressApplicationTitle",
        "-d", r.instance.cwd,
        "cmd.exe", "/k", "call", r.script_path,
    ]


def _cmd_quote(arg: str) -> str:
    if arg and not any(c in arg for c in ' \t"&^<>|'):
        return arg
    return '"' + arg.replace('"', "") + '"'


def _launch_wt(argv: list[str], dry: bool, via_start: bool = False) -> None:
    if dry:
        return
    if via_start and PLATFORM == "win32":
        line = 'start "" ' + " ".join(_cmd_quote(a) for a in argv)
        subprocess.Popen(line, shell=True)
    else:
        subprocess.Popen(argv, close_fds=True)


def _grid_dims(n: int, layout: str) -> tuple[int, int]:
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
    cols, rows = _grid_dims(len(handles), layout)
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
    argv += ["new-tab"] + _wt_pane_args(rendered[0])
    m = n
    order = list(range(n - 1, 0, -1))
    for idx, inst_index in enumerate(order):
        if idx > 0:
            argv += [";", "move-focus", back]
        size = 1.0 / m
        argv += [";", "split-pane", flag, "--size", f"{size:.4f}"] + _wt_pane_args(rendered[inst_index])
        m -= 1
    if not dry:
        subprocess.Popen(argv, close_fds=True)
    return [" ".join(argv)]


def deploy_tabs(rendered: list[Rendered], dry: bool) -> list[str]:
    if not rendered:
        return []
    argv: list[str] = ["wt.exe", "-w", "new", "new-tab"] + _wt_pane_args(rendered[0])
    for r in rendered[1:]:
        argv += [";", "new-tab"] + _wt_pane_args(r)
    if not dry:
        subprocess.Popen(argv, close_fds=True)
    return [" ".join(argv)]


def deploy_tabs_here(rendered: list[Rendered], dry: bool) -> list[str]:
    if not rendered:
        return []
    inside_wt = bool(os.environ.get("WT_SESSION"))
    window = "0" if inside_wt else "new"
    argv: list[str] = ["wt.exe", "-w", window, "new-tab"] + _wt_pane_args(rendered[0])
    for r in rendered[1:]:
        argv += [";", "new-tab"] + _wt_pane_args(r)
    _launch_wt(argv, dry, via_start=inside_wt)
    return [" ".join(argv)]


def deploy_separate_windows(rendered: list[Rendered], layout: str, dry: bool) -> list[str]:
    if not rendered:
        return []
    titles = {f"{r.instance.name}": r for r in rendered}
    commands = [" ".join(_wt_window_args(r)) for r in rendered]
    if dry:
        lines = [f"# ventanas separadas ({_grid_dims(len(rendered), layout)[0]}x{_grid_dims(len(rendered), layout)[1]})"]
        lines += commands
        return lines
    previous = {hwnd for hwnd, _ in _enum_cascadia_windows()}
    for r in rendered:
        subprocess.Popen(_wt_window_args(r), close_fds=True)
    handles = _wait_windows(set(titles.keys()), previous)
    ordered = [handles[title] for title in titles if title in handles]
    if ordered:
        _tile_windows(ordered, layout)
    return commands


def deploy_linux(rendered: list[Rendered], layout: str, dry: bool) -> list[str]:
    term = os.environ.get("TERMINAL")
    candidates = [term] if term else []
    candidates += ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "alacritty", "kitty", "xterm"]
    chosen = next((c for c in candidates if c and shutil.which(c)), None)
    if chosen is None:
        raise WorkyError("no se encontro un emulador de terminal para desplegar")
    launched: list[str] = []
    for r in rendered:
        script = f'cd {shlex.quote(r.instance.cwd)} && exec bash {shlex.quote(r.script_path)}'
        if "gnome-terminal" in chosen:
            cmd = [chosen, "--title", f"{r.instance.name}", "--", "bash", "-c", script]
        else:
            cmd = [chosen, "-e", "bash", "-c", script]
        launched.append(" ".join(shlex.quote(c) for c in cmd))
        if not dry:
            subprocess.Popen(cmd, close_fds=True)
    return launched



# ---------------------------------------------------------------------------
# Kill helpers
# ---------------------------------------------------------------------------

def kill_processes(pattern: str) -> None:
    if PLATFORM == "win32":
        ps = (
            "Get-CimInstance Win32_Process | "
            f"Where-Object {{ $_.CommandLine -like '*{pattern}*' -and $_.ProcessId -ne $PID "
            f"-and $_.ProcessId -ne {os.getpid()} }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    else:
        subprocess.run(["pkill", "-f", pattern], check=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def find_default_file() -> str:
    if os.path.exists("workspace.worky"):
        return "workspace.worky"
    here = sorted(Path(".").glob("*.worky"))
    if here:
        return str(here[0])
    raise WorkyError("no se encontro ningun archivo .worky en el directorio actual")


def main(argv: list[str]) -> int:
    if "--kill" in argv or "--kill-all" in argv:
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

    file_path = None
    script_args: list[str] = []
    layout = "auto"
    display = "tabs-here"
    dry = False
    dump = False
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
    worky_path = os.path.abspath(__file__)

    rendered = [render_script(inst, runid, run_dir, worky_path, interp.eval) for inst in interp.instances]

    print(f"worky: {len(interp.instances)} instancia(s) [{PLATFORM}] {display} -> {runid}")
    for r in rendered:
        print(f"  - {r.instance.name}  @  {r.instance.cwd}")
        if dump:
            print("    " + r.body.replace("\n", "\n    ").rstrip())

    if PLATFORM == "win32":
        if display == "one-window":
            lines = deploy_one_window(rendered, "columns" if layout == "auto" else layout, dry)
        elif display == "tabs":
            lines = deploy_tabs(rendered, dry)
        elif display == "tabs-here":
            lines = deploy_tabs_here(rendered, dry)
            if not os.environ.get("WT_SESSION") and not dry:
                print("worky: no se detecto Windows Terminal; se abrio una ventana nueva")
        else:
            lines = deploy_separate_windows(rendered, layout, dry)
        if dry:
            for line in lines:
                print(line)
    else:
        if display in ("one-window", "tabs-here"):
            print("worky: modo no soportado en esta plataforma; se abren ventanas separadas")
        lines = deploy_linux(rendered, layout, dry)
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
        "opciones:\n"
        "  --layout auto|columns|rows|grid   disposicion (auto por defecto)\n"
        "  --dry-run                         muestra que se ejecutaria sin desplegar\n"
        "  --dump                            muestra los scripts generados\n"
        "\n"
        "control:\n"
        "  worky --kill <nombre> --run <id>\n"
        "  worky --kill-all --run <id>\n"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except WorkyError as exc:
        print(f"worky: error: {exc}", file=sys.stderr)
        raise SystemExit(1)
