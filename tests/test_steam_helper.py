import struct
import sys
import textwrap

import pytest

from arenahub import steam_helper
from arenahub.core import paths, steam_keys
from arenahub.core.context import Cancelled, PromptKind, TaskError

from .conftest import RecordingContext


def test_legacy_key_messages_round_trip():
    from steam.core.msg import Msg
    from steam.enums import EResult
    from steam.enums.emsg import EMsg

    steam_helper._register_messages()

    request = Msg(EMsg.ClientGetLegacyGameKey, extended=True)
    request.body.app_id = 2200
    raw = request.serialize()
    # 36-byte extended header, then the app id.
    assert struct.unpack_from("<I", raw)[0] == EMsg.ClientGetLegacyGameKey
    assert raw[36:] == struct.pack("<I", 2200)

    key = b"ABCDGHJLPRSTW237\0"
    body = struct.pack("<IiI", 2200, EResult.OK, len(key)) + key
    header = Msg(EMsg.ClientGetLegacyGameKeyResponse, extended=True).header.serialize()
    response = Msg(EMsg.ClientGetLegacyGameKeyResponse, header + body, extended=True)
    assert response.body.app_id == 2200
    assert response.body.eresult == EResult.OK
    assert response.body.key == "ABCDGHJLPRSTW237"


FAKE_HELPER = textwrap.dedent(
    """
    import json, sys
    def send(m):
        print(json.dumps(m), flush=True)
    request = json.loads(sys.stdin.readline())
    assert request["password"] == "secret"
    send({"type": "prompt", "kind": "two_factor_code", "retry": False})
    reply = json.loads(sys.stdin.readline() or "{}")
    if not reply.get("code"):
        sys.exit(2)
    if reply["code"] == "BAD":
        send({"type": "error", "result": "InvalidPassword", "message": "Rejected"})
        sys.exit(1)
    for app in request["apps"]:
        if app == 2200:
            send({"type": "key", "app": app, "result": "OK", "key": "ABCDGHJLPRSTW237"})
        else:
            send({"type": "key", "app": app, "result": "AccessDenied", "key": ""})
    send({"type": "done"})
    """
)


@pytest.fixture
def fake_helper(tmp_path, monkeypatch):
    script = tmp_path / "fake_helper.py"
    script.write_text(FAKE_HELPER)
    monkeypatch.setattr(paths, "self_command", lambda *args: [sys.executable, str(script)])


def test_fetch_keys(fake_helper):
    ctx = RecordingContext(answers=["12345"])
    results = steam_keys.fetch(ctx, "me", "secret", [2200, 2350])
    assert ctx.prompts[0].kind is PromptKind.TWO_FACTOR_CODE
    assert results[2200].ok and results[2200].key == "ABCDGHJLPRSTW237"
    assert not results[2350].ok


def test_fetch_keys_error(fake_helper):
    with pytest.raises(TaskError, match="Rejected"):
        steam_keys.fetch(RecordingContext(answers=["BAD"]), "me", "secret", [2200])


def test_fetch_keys_cancelled(fake_helper):
    with pytest.raises(Cancelled):
        steam_keys.fetch(RecordingContext(answers=[]), "me", "secret", [2200])


def test_helper_self_test_runs():
    import subprocess

    result = subprocess.run(
        paths.self_command("--steam-helper", "--self-test"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"result": "OK"' in result.stdout
