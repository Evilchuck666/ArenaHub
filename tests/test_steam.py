import hashlib
import io
import lzma
import struct
import subprocess
import sys
import textwrap
import zipfile
import zlib
from types import SimpleNamespace

import pytest

from arenahub import steam_depots, steam_helper
from arenahub.core import paths, steam
from arenahub.core.context import Cancelled, PromptKind, TaskError

from .conftest import RecordingContext

# Legacy CD key messages -----------------------------------------------------------


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


# Chunk formats --------------------------------------------------------------------

PAYLOAD = b"Quake III Arena " * 1000


def test_decode_zstd_chunk():
    import zstandard

    crc = zlib.crc32(PAYLOAD)
    body = zstandard.ZstdCompressor().compress(PAYLOAD)
    data = b"VSZa" + struct.pack("<I", crc) + body
    data += struct.pack("<Ii", crc, len(PAYLOAD)) + b"\0\0\0\0" + b"zsv"
    assert steam_depots.decode_chunk(data) == PAYLOAD


def test_decode_lzma_chunk():
    lzma_filter = {"id": lzma.FILTER_LZMA1, "dict_size": 1 << 16}
    props = lzma._encode_filter_properties(lzma_filter)
    body = lzma.compress(PAYLOAD, format=lzma.FORMAT_RAW, filters=[lzma_filter])
    data = b"VZa" + b"\0\0\0\0" + props + body
    data += b"\0" + struct.pack("<II", zlib.crc32(PAYLOAD), len(PAYLOAD)) + b"zv"
    assert steam_depots.decode_chunk(data) == PAYLOAD


def test_decode_zip_chunk():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("z", PAYLOAD)
    assert steam_depots.decode_chunk(buffer.getvalue()) == PAYLOAD


def test_decode_rejects_bad_checksum():
    import zstandard

    body = zstandard.ZstdCompressor().compress(PAYLOAD)
    data = b"VSZa\0\0\0\0" + body + struct.pack("<Ii", 1234, len(PAYLOAD)) + b"\0\0\0\0zsv"
    with pytest.raises(ValueError, match="checksum"):
        steam_depots.decode_chunk(data)


# Depot downloads ------------------------------------------------------------------


def test_relative_path():
    include = ("baseq3", "missionpack")
    assert str(steam_depots.relative_path("baseq3\\pak0.pk3", include)) == "baseq3/pak0.pk3"
    assert steam_depots.relative_path("quake3.exe", include) is None
    assert steam_depots.relative_path("Docs\\readme.txt", include) is None
    assert steam_depots.relative_path("baseq3\\..\\..\\evil", include) is None


class FakeCDN:
    """Stands in for steam-next's CDNClient: one depot, files split in chunks."""

    CHUNK = 1000

    def __init__(self, files: dict[str, bytes], licensed=(2200,), corrupt=()):
        self.licensed_app_ids = set(licensed)
        self.fetched: list[str] = []
        self.files = files
        self.corrupt = set(corrupt)

    def get_manifests(self, app_id, filter_func=None):
        if filter_func and not filter_func(2201, {}):
            return []
        manifest = SimpleNamespace(depot_id=2201)
        depot_files = []
        for name, data in self.files.items():
            chunks = [
                SimpleNamespace(offset=i, sha=f"{name}:{i}".encode(), cb_original=len(part))
                for i, part in (
                    (i, data[i : i + self.CHUNK]) for i in range(0, len(data), self.CHUNK)
                )
            ]
            depot_files.append(
                SimpleNamespace(
                    filename_raw=name,
                    is_directory=False,
                    size=len(data),
                    sha_content=hashlib.sha1(data).digest(),
                    file_mapping=SimpleNamespace(chunks=list(reversed(chunks))),
                    manifest=manifest,
                )
            )
        manifest.iter_files = lambda: iter(depot_files)
        return [manifest]


@pytest.fixture
def fake_fetch(monkeypatch):
    def fetch(cdn, app_id, depot_id, chunk):
        name, offset = chunk.sha.decode().rsplit(":", 1)
        cdn.fetched.append(name)
        data = cdn.files[name][int(offset) : int(offset) + cdn.CHUNK]
        return b"X" * len(data) if name in cdn.corrupt else data

    monkeypatch.setattr(steam_depots, "fetch_chunk", fetch)


FILES = {
    "baseq3\\pak0.pk3": bytes(range(256)) * 20,
    "baseq3\\q3config.cfg": b"seta name Steam\n",
    "quake3.exe": b"MZ",
}


def test_download_writes_included_files(tmp_path, fake_fetch):
    cdn = FakeCDN(FILES)
    seen = []
    handled: set[int] = set()
    written = steam_depots.download_app(
        cdn, 2200, tmp_path, ("baseq3",), handled, lambda *a: seen.append(a)
    )
    assert sorted(written) == ["baseq3/pak0.pk3", "baseq3/q3config.cfg"]
    assert (tmp_path / "baseq3" / "pak0.pk3").read_bytes() == FILES["baseq3\\pak0.pk3"]
    assert not (tmp_path / "quake3.exe").exists()
    assert not list(tmp_path.rglob("*" + steam_depots.PART_SUFFIX))
    assert handled == {2201}
    assert seen[-1][0] == seen[-1][1]  # progress reaches the total


def test_download_verifies_instead_of_downloading_again(tmp_path, fake_fetch):
    steam_depots.download_app(FakeCDN(FILES), 2200, tmp_path, ("baseq3",), set(), print)
    (tmp_path / "baseq3" / "q3config.cfg").write_text("seta name Mine\n")

    cdn = FakeCDN(FILES)
    written = steam_depots.download_app(cdn, 2200, tmp_path, ("baseq3",), set(), print)
    assert written == []
    assert cdn.fetched == []
    # The user's config is never replaced.
    assert (tmp_path / "baseq3" / "q3config.cfg").read_text() == "seta name Mine\n"


def test_download_skips_shared_depots(tmp_path, fake_fetch):
    assert (
        steam_depots.download_app(FakeCDN(FILES), 2200, tmp_path, ("baseq3",), {2201}, print) == []
    )


def test_download_not_owned(tmp_path, fake_fetch):
    with pytest.raises(steam_depots.NotOwned):
        steam_depots.download_app(
            FakeCDN(FILES, licensed=()), 2200, tmp_path, ("baseq3",), set(), print
        )


def test_download_rejects_corrupted_files(tmp_path, fake_fetch):
    cdn = FakeCDN(FILES, corrupt={"baseq3\\pak0.pk3"})
    with pytest.raises(steam_depots.DepotError, match="corrupted"):
        steam_depots.download_app(cdn, 2200, tmp_path, ("baseq3",), set(), print)
    assert not (tmp_path / "baseq3" / "pak0.pk3").exists()


# Talking to the helper process ----------------------------------------------------

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
    for app in request["keys"]:
        if app == 2200:
            send({"type": "key", "app": app, "result": "OK", "key": "ABCDGHJLPRSTW237"})
        else:
            send({"type": "key", "app": app, "result": "AccessDenied", "key": ""})
    for app in request.get("download", {}).get("apps", []):
        send({"type": "app_start", "app": app})
        if app == 2200:
            send({"type": "progress", "app": app, "done": 5, "total": 10, "text": "pak0.pk3"})
            send({"type": "app", "app": app, "result": "OK", "written": 1})
        else:
            send({"type": "app", "app": app, "result": "NotOwned", "written": 0})
    send({"type": "done"})
    """
)


@pytest.fixture
def fake_helper(tmp_path, monkeypatch):
    script = tmp_path / "fake_helper.py"
    script.write_text(FAKE_HELPER)
    monkeypatch.setattr(paths, "self_command", lambda *args: [sys.executable, str(script)])


def test_run_fetches_keys_and_downloads(fake_helper, tmp_path):
    ctx = RecordingContext(answers=["12345"])
    download = steam.Download(tmp_path, (2200, 2350), ("baseq3",), {2200: "Quake III Arena"})
    result = steam.run(ctx, "me", "secret", [2200, 2350], download)

    assert ctx.prompts[0].kind is PromptKind.TWO_FACTOR_CODE
    assert result.keys[2200].ok and result.keys[2200].key == "ABCDGHJLPRSTW237"
    assert not result.keys[2350].ok
    assert result.owns(2200) and not result.owns(2350)
    assert "Downloading Quake III Arena" in ctx.stages
    assert "Downloading Steam app 2350" in ctx.stages


def test_run_error(fake_helper):
    with pytest.raises(TaskError, match="Rejected"):
        steam.run(RecordingContext(answers=["BAD"]), "me", "secret", [2200])


def test_run_cancelled(fake_helper):
    with pytest.raises(Cancelled):
        steam.run(RecordingContext(answers=[]), "me", "secret", [2200])


def test_helper_self_test_runs():
    result = subprocess.run(
        paths.self_command("--steam-helper", "--self-test"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"result": "OK"' in result.stdout
