from worky import render
from worky.deployers import windows
from worky.interpreter import Instance, Interpreter


def _rendered(tmp_path, name="demo"):
    inst = Instance(name, str(tmp_path), [])
    return render.render_script(inst, "wk1", str(tmp_path), Interpreter(".", []).eval)


def test_grid_dims():
    assert windows.grid_dims(4, "auto") == (2, 2)
    assert windows.grid_dims(3, "rows") == (1, 3)
    assert windows.grid_dims(3, "columns") == (3, 1)


def test_deploy_tabs_dry(tmp_path):
    rendered = [_rendered(tmp_path, "a"), _rendered(tmp_path, "b")]
    lines = windows.deploy_tabs(rendered, dry=True)
    assert len(lines) == 1
    assert "wt.exe" in lines[0] and lines[0].count("new-tab") == 2


def test_deploy_tabs_here_dry(tmp_path, monkeypatch):
    monkeypatch.delenv("WT_SESSION", raising=False)
    rendered = [_rendered(tmp_path, "a")]
    lines = windows.deploy_tabs_here(rendered, dry=True)
    assert "wt.exe -w new new-tab" in lines[0]


def test_deploy_separate_windows_dry(tmp_path):
    rendered = [_rendered(tmp_path, "a"), _rendered(tmp_path, "b")]
    lines = windows.deploy_separate_windows(rendered, "auto", dry=True)
    assert lines[0].startswith("# ventanas separadas")
    assert len(lines) == 3
