from worky import render
from worky.interpreter import Instance, Interpreter
from worky.nodes import Command, EnvSet, StrLit, Tool


def _eval():
    return Interpreter(".", []).eval


def test_render_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "PLATFORM", "win32")
    inst = Instance(
        "demo",
        str(tmp_path),
        [Command("echo hola"), EnvSet("FOO", StrLit("bar"), False)],
    )
    rendered = render.render_script(inst, "wk1", str(tmp_path), _eval())
    assert rendered.marker == "worky_demo.cmd"
    text = open(rendered.script_path, encoding="utf-8").read()
    assert text.startswith("@echo off\nchcp 65001 >nul\n")
    assert "set FOO=bar" in text
    assert "echo hola" in text


def test_render_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "PLATFORM", "linux")
    inst = Instance("demo", str(tmp_path), [EnvSet("FOO", StrLit("bar baz"), True)])
    rendered = render.render_script(inst, "wk1", str(tmp_path), _eval())
    assert rendered.marker == "worky_demo.sh"
    text = open(rendered.script_path, encoding="utf-8").read()
    assert text.startswith("#!/usr/bin/env bash")
    assert "export FOO='bar baz'" in text


def test_render_pause(monkeypatch):
    monkeypatch.setattr(render, "PLATFORM", "win32")
    assert render.render_tool(Tool("pause"), "wk1", _eval()) == "pause"
    monkeypatch.setattr(render, "PLATFORM", "linux")
    assert "read -r" in render.render_tool(Tool("pause"), "wk1", _eval())


def test_render_kill(monkeypatch):
    monkeypatch.setattr(render, "PLATFORM", "win32")
    line = render.render_tool(Tool("kill", [StrLit("all")]), "wk1", _eval())
    assert "--kill-all" in line and "--run wk1" in line
    line = render.render_tool(Tool("kill", [StrLit("dev")]), "wk1", _eval())
    assert "--kill" in line and "dev" in line


def test_unknown_tool(monkeypatch):
    import pytest

    from worky.errors import WorkyError

    monkeypatch.setattr(render, "PLATFORM", "win32")
    with pytest.raises(WorkyError):
        render.render_tool(Tool("nope"), "wk1", _eval())
