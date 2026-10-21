import pytest

from arenahub.core.archive import extract, merge_tree
from arenahub.core.catalog import Rule
from arenahub.core.context import TaskError

from .conftest import make_zip


def test_extract_with_rule(tmp_path, ctx):
    archive = make_zip(
        tmp_path / "mod.zip",
        {
            "arena/maps.pk3": "pk3",
            "arena/qagamex86.dll": "dll",
            "arena/Thumbs.db": "junk",
            "ra3.exe": "exe",
        },
    )
    dest = tmp_path / "install"
    rule = Rule(include=("arena/*",), exclude=("*.dll", "*.exe", "thumbs.db"))
    written = extract(ctx, archive, dest, rule)
    assert [p.relative_to(dest).as_posix() for p in written] == ["arena/maps.pk3"]


def test_extract_into_target(tmp_path, ctx):
    archive = make_zip(tmp_path / "maps.zip", {"map_cpm1.pk3": "x", "readme.txt": "y"})
    extract(ctx, archive, tmp_path / "q3", Rule(target="baseq3", include=("*.pk3",)))
    assert (tmp_path / "q3" / "baseq3" / "map_cpm1.pk3").is_file()
    assert not (tmp_path / "q3" / "baseq3" / "readme.txt").exists()


@pytest.mark.parametrize("name", ["../evil.pk3", "/abs/evil.pk3", "C:/evil.pk3", "a/../../evil"])
def test_extract_rejects_unsafe_paths(tmp_path, ctx, name):
    archive = make_zip(tmp_path / "evil.zip", {name: "x"})
    with pytest.raises(TaskError):
        extract(ctx, archive, tmp_path / "dest")


def test_extract_rejects_non_zip(tmp_path, ctx):
    bad = tmp_path / "bad.zip"
    bad.write_text("not a zip")
    with pytest.raises(TaskError):
        extract(ctx, bad, tmp_path / "dest")


def test_merge_tree_replaces_files(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    (src / "sub").mkdir(parents=True)
    (src / "pak0.pk3").write_text("new")
    (src / "sub" / "x.cfg").write_text("cfg")
    dest.mkdir()
    (dest / "pak0.pk3").write_text("old")
    (dest / "map_cpm1.pk3").write_text("keep")

    merge_tree(src, dest)

    assert (dest / "pak0.pk3").read_text() == "new"
    assert (dest / "sub" / "x.cfg").read_text() == "cfg"
    assert (dest / "map_cpm1.pk3").read_text() == "keep"
