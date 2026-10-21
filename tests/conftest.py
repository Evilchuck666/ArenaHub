import os
import zipfile
from pathlib import Path

import pytest

from arenahub.core.context import Context

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class RecordingContext(Context):
    """Context that records everything and answers prompts from a list."""

    def __init__(self, answers=()):
        super().__init__()
        self.logs: list[str] = []
        self.stages: list[str] = []
        self.prompts = []
        self.answers = list(answers)

    def log(self, message):
        self.logs.append(message)

    def stage(self, title):
        self.stages.append(title)

    def ask(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else None


@pytest.fixture
def ctx():
    return RecordingContext()


def make_zip(path: Path, files: dict[str, bytes | str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return path
