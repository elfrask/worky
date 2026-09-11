"""interpretacion del AST y construccion de instancias."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from worky.errors import WorkyError
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
from worky.platforms import PLATFORM, fmt_value


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
                raise WorkyError(
                    "solo 'in', 'run' y asignaciones estan permitidos en el nivel superior"
                )

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
                raise WorkyError(
                    "solo comandos, 'set'/'export' y herramientas estan permitidos en bloques 'os'"
                )

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
