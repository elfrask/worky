"""nodos del AST del lenguaje .worky."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    args: list[Any] = field(default_factory=list)
    body: list[Any] | None = None


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
