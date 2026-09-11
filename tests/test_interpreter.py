from worky.interpreter import Interpreter
from worky.nodes import Command, StrLit, VarRef
from worky.parser import Parser


def _interp(args=None, create_dirs=False):
    return Interpreter(".", args or [], create_dirs=create_dirs)


def test_variables_and_interpolation():
    interp = _interp()
    body = Parser('$name = "worky"\n$msg = "hola $name"\n').parse()
    interp.run(body, ".")
    assert interp.vars["msg"] == "hola worky"


def test_script_args():
    interp = _interp(["uno", "dos"])
    body = Parser("$first = $~1\n$rest = $*\n").parse()
    interp.run(body, ".")
    assert interp.vars["first"] == "uno"
    assert interp.vars["rest"] == ["uno", "dos"]


def test_array_spread():
    interp = _interp(["a"])
    body = Parser('$all = ["x", ...$*]\n').parse()
    interp.run(body, ".")
    assert interp.vars["all"] == ["x", "a"]


def test_instances_and_unique_names():
    src = 'run "dev" {\n  os: all {\n    echo hola\n  }\n}\nrun "dev" {\n  os: all {\n    echo hola\n  }\n}\n'
    interp = _interp()
    interp.run(Parser(src).parse(), ".")
    assert [inst.name for inst in interp.instances] == ["dev", "dev-2"]


def test_os_filtering(monkeypatch):
    import worky.interpreter as interpreter

    monkeypatch.setattr(interpreter, "PLATFORM", "win32")
    src = "run {\n  os: win32 {\n    echo win\n  }\n  os: linux {\n    echo lin\n  }\n}\n"
    interp = _interp()
    interp.run(Parser(src).parse(), ".")
    actions = interp.instances[0].actions
    assert [a.text for a in actions] == ["echo win"]


def test_tool_kept_in_actions():
    src = "run {\n  /pause\n}\n"
    interp = _interp()
    interp.run(Parser(src).parse(), ".")
    assert interp.instances[0].actions[0].name == "pause"


def test_top_level_rejects_command():
    import pytest

    from worky.errors import WorkyError

    with pytest.raises(WorkyError):
        _interp().run([Command("echo hola")], ".")
