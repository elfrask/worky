"""consola interactiva worky --cli."""

from __future__ import annotations

from worky.errors import WorkyError


def run_cli(file_path: str | None = None) -> None:
    try:
        from worky.tui.app import WorkyCliApp
    except ImportError as exc:  # pragma: no cover - depende de extras
        raise WorkyError(
            "worky --cli requiere dependencias opcionales: "
            "pip install 'worky[cli]' (textual, pyte, pywinpty)"
        ) from exc
    app = WorkyCliApp(file_path=file_path)
    app.run()


__all__ = ["run_cli"]
