"""Steam client process that fetches legacy CD keys.

SteamCMD cannot read CD keys, so ArenaHub logs in to Steam itself (with
steam-next) and asks for them the way the Steam client's "CD Keys" dialog does.

steam-next is built on gevent, which needs monkey-patching that does not mix
with Qt. That is why this runs as a separate process: the same executable
started with --steam-helper. It talks JSON lines over stdin/stdout:

    in:  {"username": ..., "password": ..., "apps": [2200, 2350]}
    out: {"type": "prompt", "kind": "email_code" | "two_factor_code", "retry": bool}
    in:  {"code": "..."}            (or {} to give up)
    out: {"type": "key", "app": 2200, "result": "OK", "key": "..."}
    out: {"type": "done"} | {"type": "error", "result": "InvalidPassword", "message": ...}

The password only ever travels through stdin and is never stored.
"""

from __future__ import annotations

import json
import struct
import sys

EXIT_OK, EXIT_ERROR, EXIT_CANCELLED = 0, 1, 2

LOGIN_ATTEMPTS = 3
KEY_TIMEOUT = 15


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()

    import steam.monkey

    steam.monkey.patch_minimal()

    try:
        return Helper().run()
    except KeyboardInterrupt:
        return EXIT_CANCELLED


def self_test() -> int:
    """Check that everything the helper needs can be imported (used on frozen builds)."""
    import steam.monkey

    steam.monkey.patch_minimal()
    from steam.client import SteamClient  # noqa: F401

    _register_messages()
    emit({"type": "self-test", "result": "OK"})
    return EXIT_OK


def emit(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _register_messages():
    """Teach steam-next the two legacy key messages, which it does not define.

    StructMessage subclasses register themselves for the EMsg with their name.
    The layout comes from SteamKit2's steammsg.steamd.
    """
    from steam.core.msg.structs import StructMessage
    from steam.enums import EResult

    class ClientGetLegacyGameKey(StructMessage):
        app_id = 0

        def serialize(self):
            return struct.pack("<I", self.app_id)

        def load(self, data):
            (self.app_id,) = struct.unpack_from("<I", data)

    class ClientGetLegacyGameKeyResponse(StructMessage):
        app_id = 0
        eresult = EResult.Invalid
        key = ""

        def serialize(self):
            raw = self.key.encode("ascii") + b"\0"
            return struct.pack("<IiI", self.app_id, self.eresult, len(raw)) + raw

        def load(self, data):
            self.app_id, result, length = struct.unpack_from("<IiI", data)
            self.eresult = EResult(result)
            raw = data[12 : 12 + length]
            self.key = raw.split(b"\0", 1)[0].decode("ascii", "replace")

    return ClientGetLegacyGameKey, ClientGetLegacyGameKeyResponse


class Helper:
    def __init__(self) -> None:
        from gevent import get_hub
        from steam.client import SteamClient

        _register_messages()
        self._hub = get_hub()
        self.client = SteamClient()

    def read(self) -> dict:
        # Read stdin on a real thread so gevent keeps the connection alive meanwhile.
        line = self._hub.threadpool.apply(sys.stdin.readline)
        if not line:
            return {}
        return json.loads(line)

    def run(self) -> int:
        request = self.read()
        username = request.get("username", "")
        password = request.pop("password", "")
        if not username or not password:
            emit({"type": "error", "result": "InvalidParameter", "message": "Missing credentials"})
            return EXIT_ERROR

        status = self.login(username, password)
        del password
        if status != EXIT_OK:
            return status

        for app_id in request.get("apps", []):
            result, key = self.legacy_key(int(app_id))
            emit({"type": "key", "app": int(app_id), "result": result, "key": key})

        self.client.logout()
        emit({"type": "done"})
        return EXIT_OK

    def login(self, username: str, password: str) -> int:
        from steam.enums import EResult

        email_results = (EResult.AccountLogonDenied, EResult.InvalidLoginAuthCode)
        code_results = (EResult.AccountLoginDeniedNeedTwoFactor, EResult.TwoFactorCodeMismatch)
        transient = (EResult.Fail, EResult.ServiceUnavailable, EResult.TryAnotherCM)

        codes: dict[str, str] = {}
        failures = 0

        while True:
            result = self.client.login(username, password, **codes)
            if result == EResult.OK:
                return EXIT_OK

            if result in transient and failures < LOGIN_ATTEMPTS:
                failures += 1
                continue

            if result in email_results:
                kind, argument = "email_code", "auth_code"
            elif result in code_results:
                kind, argument = "two_factor_code", "two_factor_code"
            else:
                emit({"type": "error", "result": result.name, "message": _describe(result)})
                return EXIT_ERROR

            emit({"type": "prompt", "kind": kind, "retry": bool(codes)})
            code = self.read().get("code", "").strip()
            if not code:
                return EXIT_CANCELLED
            codes = {argument: code}

    def legacy_key(self, app_id: int) -> tuple[str, str]:
        from steam.core.msg import Msg
        from steam.enums import EResult
        from steam.enums.emsg import EMsg

        message = Msg(EMsg.ClientGetLegacyGameKey, extended=True)
        message.body.app_id = app_id
        response = self.client.send_job_and_wait(message, timeout=KEY_TIMEOUT)

        if response is None:
            return "Timeout", ""
        ok = response.eresult == EResult.OK
        return response.eresult.name, response.key if ok else ""


def _describe(result) -> str:
    from steam.enums import EResult

    return {
        EResult.InvalidPassword: "Steam rejected the username or password.",
        EResult.RateLimitExceeded: "Steam is limiting login attempts. Wait a while and try again.",
        EResult.AccountLoginDeniedThrottle: "Too many login attempts. Wait a while and try again.",
        EResult.ServiceUnavailable: "Steam is not reachable right now. Try again later.",
    }.get(result, f"Steam login failed ({result.name}).")
