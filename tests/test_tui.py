import asyncio

from worky.parser import Parser
from worky.tui.emulator import TerminalEmulator
from worky.tui.save import render_workspace
from worky.tui.session import script_spec, shell_spec, specs_from_file
from worky.tui.widgets import key_to_text


class FakeSession:
    def __init__(self, argv, cwd):
        self.argv = argv
        self.cwd = cwd
        self.written = []

    def read(self, size=65536):
        return b""

    def write(self, data):
        self.written.append(data)

    def resize(self, cols, rows):
        pass

    def isalive(self):
        return False

    def terminate(self):
        pass


def test_key_to_text():
    assert key_to_text("a") == "a"
    assert key_to_text("enter") == "\r"
    assert key_to_text("up") == "\x1b[A"
    assert key_to_text("ctrl+c") == "\x03"
    assert key_to_text("space") == " "
    assert key_to_text("f5") is None


def test_emulator_renders_text():
    emu = TerminalEmulator(20, 3)
    emu.feed(b"hola mundo")
    text = emu.render()
    plain = text.plain
    assert plain.splitlines()[0].rstrip() == "hola mundo"


def test_shell_spec_builds_argv():
    spec = shell_spec("s", ".", "git status")
    assert spec.command == "git status"
    assert spec.argv


def test_render_workspace_roundtrip(tmp_path):
    specs = [
        shell_spec("uno", str(tmp_path)),
        shell_spec("dos", str(tmp_path), "pnpm run dev"),
    ]
    text = render_workspace(specs)
    body = Parser(text).parse()
    assert len(body) == 2
    assert "/shell pnpm run dev" in text
    assert "/shell" in text


def test_specs_from_file(tmp_path):
    path = tmp_path / "w.worky"
    path.write_text(
        'in "./" {\n  run "inst" {\n    os: all {\n      echo hola\n    }\n  }\n}\n',
        encoding="utf-8",
    )
    specs = specs_from_file(str(path))
    assert len(specs) == 1
    assert specs[0].name == "inst"
    assert "echo hola" in (specs[0].raw or "")


def test_app_smoke():
    async def main():
        from textual.widgets import OptionList, TabbedContent

        from worky.tui.app import WorkyCliApp
        from worky.tui.palette import CommandPalette

        def factory(argv, cwd):
            return FakeSession(argv, cwd)

        app = WorkyCliApp(file_path=None, session_factory=factory)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()

            # Ctrl+P abre la paleta y las flechas navegan las opciones
            await pilot.press("ctrl+p")
            await pilot.pause()
            assert isinstance(app.screen, CommandPalette)
            option_list = app.screen.query_one(OptionList)
            assert option_list.highlighted == 0
            await pilot.press("down")
            await pilot.press("down")
            await pilot.pause()
            assert option_list.highlighted == 2
            await pilot.press("up")
            await pilot.pause()
            assert option_list.highlighted == 1
            await pilot.press("escape")
            await pilot.pause()

            # nuevas sesiones
            await pilot.press("ctrl+t")
            await pilot.pause()
            assert len(app._records) == 2
            await pilot.press("ctrl+n")
            await pilot.pause()
            assert len(app._records) == 3

            # Ctrl+flechas cambian de shell
            tabs = app.query_one(TabbedContent)
            ids = list(app._records.keys())
            tabs.active = ids[0]
            await pilot.pause()
            assert tabs.active_pane.id == ids[0]
            await pilot.press("ctrl+right")
            await pilot.pause()
            assert tabs.active_pane.id == ids[1]
            await pilot.press("ctrl+right")
            await pilot.pause()
            assert tabs.active_pane.id == ids[2]
            await pilot.press("ctrl+right")
            await pilot.pause()
            assert tabs.active_pane.id == ids[0]
            await pilot.press("ctrl+left")
            await pilot.pause()
            assert tabs.active_pane.id == ids[2]

            # cerrar
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert len(app._records) == 2

    asyncio.run(main())
