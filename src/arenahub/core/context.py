"""The link between long-running tasks and whoever is watching them (GUI or tests)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum


class Cancelled(Exception):
    """Raised inside a task once the user has asked to stop it."""


class TaskError(Exception):
    """A failure with a message meant for the user."""


class PromptKind(Enum):
    EMAIL_CODE = "email_code"
    TWO_FACTOR_CODE = "two_factor_code"


@dataclass(frozen=True)
class Prompt:
    kind: PromptKind
    message: str
    retry: bool = False


class Context:
    """Reports progress and asks questions on behalf of a running task.

    The default implementation only records what happens, which is what the
    tests need. The GUI subclasses it and forwards everything to the window.
    """

    def __init__(self) -> None:
        self._cancel = threading.Event()

    # Cancellation -----------------------------------------------------------

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check(self) -> None:
        """Stop the task here if it was cancelled."""
        if self._cancel.is_set():
            raise Cancelled()

    # Reporting --------------------------------------------------------------

    def log(self, message: str) -> None:
        """A line for the activity log."""

    def stage(self, title: str) -> None:
        """A new step of the task has started."""

    def progress(self, fraction: float | None, detail: str = "") -> None:
        """Progress of the current step, from 0 to 1, or None when unknown."""

    # Questions --------------------------------------------------------------

    def ask(self, prompt: Prompt) -> str | None:
        """Ask the user for a secret or a code. None means the user gave up."""
        return None
