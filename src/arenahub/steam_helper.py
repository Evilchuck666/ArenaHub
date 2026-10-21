"""Steam client process: one login to fetch the CD keys and download the game.

ArenaHub logs in to Steam with steam-next, asks for the legacy CD keys the way
the Steam client's "CD Keys" dialog does, and downloads the depots from Steam's
content network (see steam_depots). One login covers everything.

steam-next is built on gevent, which needs monkey-patching that does not mix
with Qt. That is why this runs as a separate process: the same executable
started with --steam-helper. It talks JSON lines over stdin/stdout:

    in:  {"username": ..., "password": ..., "keys": [2200, 2350],
          "download": {"dir": ..., "apps": [2200, 2350], "include": ["baseq3", ...]}}
    out: {"type": "prompt", "kind": "email_code" | "two_factor_code", "retry": bool}
    in:  {"code": "..."}            (or {} to give up)
    out: {"type": "key", "app": 2200, "result": "OK", "key": "..."}
    out: {"type": "app_start", "app": 2200}
    out: {"type": "progress", "app": 2200, "done": bytes, "total": bytes, "text": ...}
    out: {"type": "app", "app": 2350, "result": "OK" | "NotOwned", "written": n}
    out: {"type": "done"} | {"type": "error", "result": "InvalidPassword", "message": ...}

The password only ever travels through stdin and is never stored.
"""

from __future__ import annotations

import json
import struct
import sys
import time
from pathlib import Path

EXIT_OK, EXIT_ERROR, EXIT_CANCELLED = 0, 1, 2

LOGIN_ATTEMPTS = 3
KEY_TIMEOUT = 15
LICENSE_TIMEOUT = 20


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
    """Check that everything the helper needs is there and works (used on frozen builds)."""
    import zlib

    import steam.monkey

    steam.monkey.patch_minimal()
    import zstandard
    from gevent.pool import Pool  # noqa: F401
    from steam.client import SteamClient  # noqa: F401
    from steam.client.cdn import CDNClient  # noqa: F401

    from arenahub import steam_depots

    _register_messages()

    # Decode a zstd chunk, the format Steam uses today, to exercise the C extension.
    payload = b"ArenaHub" * 64
    crc = zlib.crc32(payload)
    chunk = b"VSZa" + struct.pack("<I", crc) + zstandard.ZstdCompressor().compress(payload)
    chunk += struct.pack("<Ii", crc, len(payload)) + b"\0\0\0\0zsv"
    if steam_depots.decode_chunk(chunk) != payload:
        emit({"type": "self-test", "result": "Failed", "message": "zstd chunk decoding"})
        return EXIT_ERROR

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

        for app_id in request.get("keys", []):
            result, key = self.legacy_key(int(app_id))
            emit({"type": "key", "app": int(app_id), "result": result, "key": key})

        if download := request.get("download"):
            status = self.download(download)
            if status != EXIT_OK:
                return status

        self.client.logout()
        emit({"type": "done"})
        return EXIT_OK

    def wait_for_licenses(self) -> None:
        """Steam sends the account's licenses right after logon; ownership needs them."""
        deadline = time.monotonic() + LICENSE_TIMEOUT
        while not self.client.licenses and time.monotonic() < deadline:
            self.client.sleep(0.2)

    def download(self, request: dict) -> int:
        from steam.client.cdn import CDNClient

        from arenahub import steam_depots

        self.wait_for_licenses()
        try:
            cdn = CDNClient(self.client)
        except Exception as exc:  # noqa: BLE001 - steam-next raises several error types
            emit({"type": "error", "result": "CDN", "message": f"Steam content servers: {exc}"})
            return EXIT_ERROR

        dest = Path(request["dir"])
        include = tuple(name.lower() for name in request.get("include", []))
        handled_depots: set[int] = set()

        for app_id in map(int, request.get("apps", [])):
            emit({"type": "app_start", "app": app_id})

            def progress(done, total, text, app_id=app_id):
                emit(
                    {"type": "progress", "app": app_id, "done": done, "total": total, "text": text}
                )

            try:
                written = steam_depots.download_app(
                    cdn, app_id, dest, include, handled_depots, progress
                )
            except steam_depots.NotOwned:
                emit({"type": "app", "app": app_id, "result": "NotOwned", "written": 0})
                continue
            except steam_depots.DepotError as exc:
                emit({"type": "error", "result": "DepotError", "message": str(exc)})
                return EXIT_ERROR
            emit({"type": "app", "app": app_id, "result": "OK", "written": len(written)})
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
