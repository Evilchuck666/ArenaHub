import sys
import textwrap

import pytest

from arenahub.core import steamcmd
from arenahub.core.context import PromptKind, TaskError

from .conftest import RecordingContext


def test_parser_lines_progress_and_prompts():
    parser = steamcmd.OutputParser()
    events = parser.feed("Logging in user 'me' to Steam Public...\r\npass")
    assert [e.kind for e in events] == ["line"]
    events = parser.feed("word: ")
    assert events[0].kind == "prompt" and events[0].prompt is PromptKind.PASSWORD

    events = parser.feed(
        " Update state (0x61) downloading, progress: 42.50 (218211 / 513401161)\n"
        "[ 33%] Downloading update (1,234 of 40,000 KB)...\n"
        "Two-factor code:"
    )
    assert events[0].kind == "progress" and events[0].fraction == pytest.approx(0.425)
    assert events[0].text == "Downloading"
    assert events[1].fraction == pytest.approx(0.33)
    assert events[2].prompt is PromptKind.TWO_FACTOR_CODE


def test_explain_failures():
    assert "does not own" in steamcmd.explain(
        ["ERROR! Failed to install app '2200' (No subscription)"]
    )
    assert "rejected" in steamcmd.explain(["FAILED (Invalid Password)"])
    assert steamcmd.explain(["nothing useful"]) == "SteamCMD did not finish the download."


FAKE_STEAMCMD = textwrap.dedent(
    """
    import sys
    sys.stdout.write("Logging in user 'me' to Steam Public...\\npassword: ")
    sys.stdout.flush()
    password = input()
    if password != "hunter2":
        print("FAILED (Invalid Password)")
        sys.exit(5)
    sys.stdout.write("Two-factor code:")
    sys.stdout.flush()
    code = input()
    if code != "ABCDE":
        print("FAILED (Two-factor code mismatch)")
        sys.exit(5)
    print("OK")
    print(" Update state (0x61) downloading, progress: 50.00 (1 / 2)")
    print("Success! App '2200' fully installed.")
    """
)


@pytest.fixture
def fake_steamcmd(tmp_path):
    script = tmp_path / "fake_steamcmd.py"
    script.write_text(FAKE_STEAMCMD)
    launcher = tmp_path / "steamcmd.sh"
    launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    launcher.chmod(0o755)
    return launcher


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX pseudo-terminal test")
def test_download_app_answers_prompts(tmp_path, fake_steamcmd):
    ctx = RecordingContext(answers=["ABCDE"])
    steamcmd.download_app(ctx, fake_steamcmd, 2200, tmp_path / "depot", "me", "hunter2")
    # The password came from the options; only the code was asked.
    assert [p.kind for p in ctx.prompts] == [PromptKind.TWO_FACTOR_CODE]
    assert any("fully installed" in line for line in ctx.logs)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX pseudo-terminal test")
def test_download_app_not_owned(tmp_path):
    script = tmp_path / "steamcmd.sh"
    script.write_text(
        "#!/bin/sh\n"
        "echo \"Logging in user 'me' to Steam Public...OK\"\n"
        "echo \"ERROR! Failed to install app '2350' (No subscription)\"\n"
        "exit 8\n"
    )
    script.chmod(0o755)
    with pytest.raises(steamcmd.NotOwned) as caught:
        steamcmd.download_app(RecordingContext(), script, 2350, tmp_path / "depot", "me", None)
    assert caught.value.app_id == 2350
    assert "does not own" in str(caught.value)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX pseudo-terminal test")
def test_download_app_reports_failure(tmp_path, fake_steamcmd):
    ctx = RecordingContext(answers=["WRONG"])
    with pytest.raises(TaskError, match="not accepted"):
        steamcmd.download_app(ctx, fake_steamcmd, 2200, tmp_path / "depot", "me", "hunter2")
