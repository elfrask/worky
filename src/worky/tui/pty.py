"""sesiones PTY multiplataforma para la consola embebida."""

from __future__ import annotations

import os
import subprocess
from typing import Sequence

from worky.platforms import PLATFORM


class PtySession:
    """interfaz comun de una terminal con proceso real."""

    def read(self, size: int = 65536) -> bytes:
        raise NotImplementedError

    def write(self, data: str) -> None:
        raise NotImplementedError

    def resize(self, cols: int, rows: int) -> None:
        raise NotImplementedError

    def isalive(self) -> bool:
        raise NotImplementedError

    def terminate(self) -> None:
        raise NotImplementedError


class WinPtySession(PtySession):
    def __init__(
        self,
        argv: Sequence[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        cols: int = 80,
        rows: int = 24,
    ):
        import winpty

        command = argv if isinstance(argv, str) else subprocess.list2cmdline(list(argv))
        self._proc = winpty.PtyProcess.spawn(
            command, cwd=cwd, env=env, dimensions=(rows, cols)
        )

    def read(self, size: int = 65536) -> bytes:
        try:
            data = self._proc.read(size)
        except EOFError:
            return b""
        except Exception:
            return b""
        if not data:
            return b""
        if isinstance(data, str):
            return data.encode("utf-8", "replace")
        return data

    def write(self, data: str) -> None:
        try:
            self._proc.write(data)
        except Exception:
            pass

    def resize(self, cols: int, rows: int) -> None:
        try:
            self._proc.setwinsize(rows, cols)
        except Exception:
            pass

    def isalive(self) -> bool:
        try:
            return bool(self._proc.isalive())
        except Exception:
            return False

    def terminate(self) -> None:
        try:
            self._proc.terminate(force=True)
            return
        except Exception:
            pass
        try:
            self._proc.kill()
        except Exception:
            pass


class PosixPtySession(PtySession):
    def __init__(
        self,
        argv: Sequence[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        cols: int = 80,
        rows: int = 24,
    ):
        import pty

        pid, fd = pty.fork()
        if pid == 0:
            try:
                if cwd:
                    os.chdir(cwd)
                os.execvpe(argv[0], list(argv), env or os.environ.copy())
            except Exception:
                os._exit(127)
        self._pid = pid
        self._fd = fd
        self.resize(cols, rows)

    def read(self, size: int = 65536) -> bytes:
        try:
            return os.read(self._fd, size)
        except OSError:
            return b""

    def write(self, data: str) -> None:
        try:
            os.write(self._fd, data.encode("utf-8", "replace"))
        except OSError:
            pass

    def resize(self, cols: int, rows: int) -> None:
        import fcntl
        import struct
        import termios

        try:
            fcntl.ioctl(self._fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except Exception:
            pass

    def isalive(self) -> bool:
        try:
            pid, _status = os.waitpid(self._pid, os.WNOHANG)
        except ChildProcessError:
            return False
        return pid == 0

    def terminate(self) -> None:
        import signal

        try:
            os.kill(self._pid, signal.SIGTERM)
        except Exception:
            pass


def create_session(
    argv: Sequence[str],
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    cols: int = 80,
    rows: int = 24,
) -> PtySession:
    if PLATFORM == "win32":
        return WinPtySession(argv, cwd=cwd, env=env, cols=cols, rows=rows)
    return PosixPtySession(argv, cwd=cwd, env=env, cols=cols, rows=rows)
