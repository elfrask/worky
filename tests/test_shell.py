from worky import render
from worky.interpreter import Interpreter
from worky.nodes import Command, StrLit, Tool


def _eval():
    return Interpreter(".", []).eval


def test_shell_windows(monkeypatch):
    monkeypatch.setattr(render, "PLATFORM", "win32")
    assert render.render_tool(Tool("shell"), "wk", _eval()) == "cmd"
    assert render.render_tool(Tool("shell", [StrLit("git status")]), "wk", _eval()) == (
        'cmd /k "git status"'
    )
    block = Tool("shell", [], [Command("git status"), Command("git pull")])
    assert render.render_tool(block, "wk", _eval()) == 'cmd /k "git status & git pull"'


def test_shell_linux(monkeypatch):
    monkeypatch.setattr(render, "PLATFORM", "linux")
    monkeypatch.setenv("SHELL", "/bin/bash")
    assert render.render_tool(Tool("shell"), "wk", _eval()) == "/bin/bash"
    assert render.render_tool(Tool("shell", [StrLit("git status")]), "wk", _eval()) == (
        "/bin/bash -c 'git status; exec /bin/bash'"
    )
    block = Tool("shell", [], [Command("echo uno"), Command("echo dos")])
    assert render.render_tool(block, "wk", _eval()) == (
        "/bin/bash -c 'echo uno; echo dos; exec /bin/bash'"
    )


def test_shell_args_join_with_space(monkeypatch):
    monkeypatch.setattr(render, "PLATFORM", "win32")
    tool = Tool("shell", [StrLit("npm"), StrLit("run"), StrLit("dev")])
    assert render.render_tool(tool, "wk", _eval()) == 'cmd /k "npm run dev"'


def test_shell_full_block_dry(monkeypatch, tmp_path):
    src = 'in "./" {\n  run "s" {\n    os: all {\n      /shell {\n        echo uno\n        echo dos\n      }\n    }\n  }\n}\n'
    from worky.interpreter import Interpreter
    from worky.parser import Parser

    monkeypatch.setattr(render, "PLATFORM", "win32")
    body = Parser(src).parse()
    interp = Interpreter(str(tmp_path), [], create_dirs=False)
    interp.run(body, str(tmp_path))
    rendered = render.render_script(interp.instances[0], "wk", str(tmp_path), interp.eval)
    assert 'cmd /k "echo uno & echo dos"' in rendered.body
