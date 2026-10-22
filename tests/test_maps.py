import hashlib
import re
import shutil

import pytest

from arenahub.core import maps, net, paths
from arenahub.core.context import TaskError

from .conftest import RecordingContext, make_zip

DATA = b"map pack data"
SHA = hashlib.sha256(DATA).hexdigest()


def pack(lvlworld: maps.LvlWorld | None = None) -> maps.MapPack:
    return maps.MapPack(
        filename="test3dm1.pk3",
        title="Test Map",
        author="Tester",
        maps=("test3dm1",),
        modes=("ffa",),
        sha256=SHA,
        size=len(DATA),
        lvlworld=lvlworld,
        page="" if lvlworld else "https://example.com/test3dm1",
    )


def test_catalog_is_pinned():
    assert len({p.filename.lower() for p in maps.MAPS}) == len(maps.MAPS)
    for p in maps.MAPS:
        assert re.fullmatch(r"[0-9a-f]{64}", p.sha256), p.filename
        assert p.title and p.author and p.maps, p.filename
        assert p.url.startswith("https://")
        if p.lvlworld:
            assert re.fullmatch(r"[0-9a-f]{64}", p.lvlworld.sha256), p.filename


def test_every_pack_has_a_backup_copy():
    for p in maps.MAPS:
        backup = paths.resource("maps", p.filename)
        assert backup.is_file(), p.filename
        assert backup.stat().st_size == p.size, p.filename
        assert p.backup_url.endswith(f"/assets/maps/{p.filename}")


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """lvlworld serves a release archive; the backup serves the bare .pk3."""
    state = {"fetched": [], "lvlworld": make_zip(tmp_path / "release.zip", {"Test3DM1.pk3": DATA})}

    def fetch(ctx, urls, dest, sha256=None, label=""):
        state["fetched"].append((urls, dest.name, sha256))
        dest.parent.mkdir(parents=True, exist_ok=True)
        if urls == ("https://files.example/release.zip",):
            shutil.copyfile(state["lvlworld"], dest)
        else:
            dest.write_bytes(DATA)
        return dest

    monkeypatch.setattr(net, "fetch", fetch)
    monkeypatch.setattr(
        maps, "lvlworld_url", lambda release_id: "https://files.example/release.zip"
    )
    return state


def install(tmp_path, monkeypatch, *packs):
    monkeypatch.setattr(maps, "MAPS", packs)
    ctx = RecordingContext()
    result = maps.install(ctx, tmp_path / "q3", tmp_path / "downloads")
    return ctx, result


def test_maps_come_from_lvlworld(tmp_path, monkeypatch, offline):
    zip_sha = net.sha256_of(offline["lvlworld"])
    _, result = install(tmp_path, monkeypatch, pack(maps.LvlWorld(42, zip_sha)))

    dest = tmp_path / "q3" / "baseq3" / "test3dm1.pk3"
    assert result.added == [dest]
    assert dest.read_bytes() == DATA
    assert offline["fetched"] == [
        (("https://files.example/release.zip",), "lvlworld-42.zip", zip_sha)
    ]


def test_backup_when_lvlworld_fails(tmp_path, monkeypatch, offline):
    def broken(release_id):
        raise TaskError("the download page has changed")

    monkeypatch.setattr(maps, "lvlworld_url", broken)
    p = pack(maps.LvlWorld(42, "0" * 64))
    ctx, _ = install(tmp_path, monkeypatch, p)

    assert offline["fetched"] == [((p.backup_url,), "test3dm1.pk3", SHA)]
    assert any("using the backup copy" in line for line in ctx.logs)


def test_backup_when_lvlworld_has_another_version(tmp_path, monkeypatch, offline):
    make_zip(offline["lvlworld"], {"test3dm1.pk3": b"older version"})
    p = pack(maps.LvlWorld(42, net.sha256_of(offline["lvlworld"])))
    install(tmp_path, monkeypatch, p)

    assert offline["fetched"][-1] == ((p.backup_url,), "test3dm1.pk3", SHA)
    assert (tmp_path / "q3" / "baseq3" / "test3dm1.pk3").read_bytes() == DATA
    assert not list((tmp_path / "q3").rglob("*.part"))


def test_packs_without_lvlworld_use_the_backup(tmp_path, monkeypatch, offline):
    p = pack()
    install(tmp_path, monkeypatch, p)
    assert offline["fetched"] == [((p.backup_url,), "test3dm1.pk3", SHA)]


def test_intact_packs_are_kept(tmp_path, monkeypatch, offline):
    dest = tmp_path / "q3" / "baseq3" / "test3dm1.pk3"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(DATA)
    _, result = install(tmp_path, monkeypatch, pack())
    assert result.added == []
    assert offline["fetched"] == []


class FakeResponse:
    def __init__(self, text="", data=None):
        self.text = text
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, page, reply):
        self.page, self.reply, self.posted = page, reply, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, timeout):
        return FakeResponse(self.page)

    def post(self, url, data, headers, timeout):
        self.posted = (url, data)
        return FakeResponse(data=self.reply)


PAGE = 'tk:["aa11","bb22"],\nf.append("z","ztn3dm2");'


def test_lvlworld_url(monkeypatch):
    reply = {"success": True, "l": "https://files.lvlworld.com", "p": "q3a/s-z", "z": "ztn3dm2.zip"}
    session = FakeSession(PAGE, {**reply, "t": "cafe"})
    monkeypatch.setattr(net, "session", lambda: session)

    assert maps.lvlworld_url(107) == "https://files.lvlworld.com/q3a/s-z/ztn3dm2.zip?cafe"
    assert session.posted == (
        "https://lvlworld.com/dload",
        {"z": "ztn3dm2", "s": "aa11", "h": "bb22", "d": "lvl"},
    )


@pytest.mark.parametrize(
    ("page", "reply", "message"),
    [
        ("<html>redesigned</html>", None, "page has changed"),
        (PAGE, {"success": False}, "no download token"),
        (PAGE, {"success": True}, "unexpected token reply"),
    ],
)
def test_lvlworld_url_errors(monkeypatch, page, reply, message):
    monkeypatch.setattr(net, "session", lambda: FakeSession(page, reply))
    with pytest.raises(TaskError, match=message):
        maps.lvlworld_url(107)


def test_failed_packs_are_reported(tmp_path, monkeypatch, offline):
    def unavailable(ctx, urls, dest, sha256=None, label=""):
        raise TaskError("404 Not Found")

    monkeypatch.setattr(net, "fetch", unavailable)
    other = maps.MapPack("other.pk3", "Other", "Tester", ("other",), (), SHA, len(DATA), page="x")
    _, result = install(tmp_path, monkeypatch, pack(), other)
    assert result.added == []
    assert result.failed == [
        "Test Map (test3dm1.pk3): 404 Not Found",
        "Other (other.pk3): 404 Not Found",
    ]
