"""Run a program inside a pseudo-terminal.

SteamCMD reads passwords and Steam Guard codes from its terminal, not from a
pipe, and buffers its output when it is not attached to one. A pseudo-terminal
(pty on Linux/macOS, ConPTY through pywinpty on Windows) solves both.
"""

from __future__ import annotations

import codecs
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path

from .paths import child_env

ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])")

COLUMNS = 400
"""Wide enough that the terminal never wraps a line of output."""


class Console:
    """A child process attached to a pseudo-terminal, read from a background thread."""

    def __init__(self, argv: list[str], cwd: Path | None = None) -> None:
        self._chunks: queue.Queue[str | None] = queue.Queue()
        if sys.platform == "win32":
            self._backend: _Backend = _WindowsBackend(argv, cwd)
        else:
            self._backend = _PosixBackend(argv, cwd)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        try:
            for chunk in self._backend.chunks():
                self._chunks.put(ANSI_ESCAPE.sub("", chunk))
        finally:
            self._chunks.put(None)

    def read(self, timeout: float) -> str | None:
        """Next piece of output, '' if nothing arrived in time, None once the output ended."""
        try:
            return self._chunks.get(timeout=timeout)
        except queue.Empty:
            return ""

    def write_line(self, text: str) -> None:
        self._backend.write(text + "\r\n" if sys.platform == "win32" else text + "\n")

    def wait(self) -> int:
        return self._backend.wait()

    def kill(self) -> None:
        self._backend.kill()


class _Backend:
    def chunks(self):
        raise NotImplementedError

    def write(self, text: str) -> None:
        raise NotImplementedError

    def wait(self) -> int:
        raise NotImplementedError

    def kill(self) -> None:
        raise NotImplementedError


class _PosixBackend(_Backend):
    def __init__(self, argv: list[str], cwd: Path | None) -> None:
        import fcntl
        import pty
        import struct
        import termios

        self._master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, COLUMNS, 0, 0))
        self._proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=child_env(),
            start_new_session=True,
            close_fds=True,
        )
        os.close(slave)

    def chunks(self):
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        while True:
            try:
                data = os.read(self._master, 4096)
            except OSError:  # EIO once the child closes the terminal
                break
            if not data:
                break
            yield decoder.decode(data)
        if tail := decoder.decode(b"", final=True):
            yield tail

    def write(self, text: str) -> None:
        os.write(self._master, text.encode())

    def wait(self) -> int:
        code = self._proc.wait()
        try:
            os.close(self._master)
        except OSError:
            pass
        return code

    def kill(self) -> None:
        if self._proc.poll() is None:
            self._proc.kill()


class _WindowsBackend(_Backend):
    def __init__(self, argv: list[str], cwd: Path | None) -> None:
        from winpty import PtyProcess

        self._proc = PtyProcess.spawn(
            subprocess.list2cmdline(argv),
            cwd=str(cwd) if cwd else None,
            env=child_env(),
            dimensions=(50, COLUMNS),
        )

    def chunks(self):
        while True:
            try:
                data = self._proc.read(4096)
            except EOFError:
                break
            if data:
                yield data
            elif not self._proc.isalive():
                break

    def write(self, text: str) -> None:
        self._proc.write(text)

    def wait(self) -> int:
        self._proc.wait()
        return self._proc.exitstatus or 0

    def kill(self) -> None:
        if self._proc.isalive():
            self._proc.terminate(force=True)
