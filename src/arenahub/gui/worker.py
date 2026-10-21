"""Runs the installation on a background thread and relays it to the window."""

from __future__ import annotations

import threading
import traceback

from PySide6.QtCore import QObject, Signal

from ..core import installer
from ..core.context import Cancelled, Context, Prompt, TaskError


class QtContext(Context):
    """Context that forwards everything to a worker's signals."""

    def __init__(self, worker: InstallWorker) -> None:
        super().__init__()
        self._worker = worker
        self._answer: str | None = None
        self._answered = threading.Event()

    def log(self, message: str) -> None:
        self._worker.log.emit(message)

    def stage(self, title: str) -> None:
        self._worker.stage.emit(title)

    def progress(self, fraction: float | None, detail: str = "") -> None:
        self._worker.progress.emit(-1.0 if fraction is None else fraction, detail)

    def ask(self, prompt: Prompt) -> str | None:
        """Block the worker thread until the window answers (see answer())."""
        self._answered.clear()
        self._worker.prompt.emit(prompt)
        while not self._answered.wait(0.2):
            if self.cancelled:
                return None
        return self._answer

    def answer(self, value: str | None) -> None:
        self._answer = value
        self._answered.set()

    def cancel(self) -> None:
        super().cancel()
        self._answered.set()


class InstallWorker(QObject):
    log = Signal(str)
    stage = Signal(str)
    progress = Signal(float, str)
    prompt = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()

    def __init__(self, options: installer.InstallOptions) -> None:
        super().__init__()
        self.options = options
        self.context = QtContext(self)

    def run(self) -> None:
        try:
            report = installer.install(self.context, self.options)
        except Cancelled:
            self.cancelled.emit()
        except TaskError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - report any bug instead of dying silently
            self.log.emit(traceback.format_exc())
            self.failed.emit(f"Unexpected error: {exc}")
        else:
            self.succeeded.emit(report)
        finally:
            # The password is only needed while installing.
            self.options.password = ""
            self.finished.emit()
