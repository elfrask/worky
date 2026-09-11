from worky.lexer import Lexer
from worky.nodes import Assign, InBlock, OsBlock, RunBlock, StrLit, Tool
from worky.parser import Parser


def test_lexer_tokens():
    kinds = [tok.kind for tok in Lexer('$x = "hi"\n').tokens()]
    assert kinds == ["VAR", "OP", "STRING", "NEWLINE", "EOF"]


def test_comments_ignored():
    body = Parser("// nada\n$x = 1\n").parse()
    assert len(body) == 1


def test_parse_assign_and_math():
    body = Parser("$sum = 5 + 1 * 2\n").parse()
    assert isinstance(body[0], Assign)
    assert body[0].name == "sum"


def test_parse_nested_blocks():
    src = 'in "./a" {\n  run "x" {\n    os: win32 {\n      echo hola\n    }\n  }\n}\n'
    body = Parser(src).parse()
    assert isinstance(body[0], InBlock)
    assert isinstance(body[0].body[0], RunBlock)
    assert isinstance(body[0].body[0].body[0], OsBlock)


def test_parse_tool_with_block():
    body = Parser("/shell {\n  git status\n  git pull\n}\n").parse()
    tool = body[0]
    assert isinstance(tool, Tool)
    assert tool.name == "shell"
    assert tool.body is not None and len(tool.body) == 2


def test_parse_tool_args():
    body = Parser('/shell "npm run dev"\n').parse()
    tool = body[0]
    assert isinstance(tool, Tool)
    assert tool.args == [StrLit("npm run dev")]
    assert tool.body is None


def test_parse_os_all_target():
    body = Parser("os: all {\n  echo hola\n}\n").parse()
    assert isinstance(body[0], OsBlock)
    assert body[0].target == "all"
