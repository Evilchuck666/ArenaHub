from arenahub.core import q3key


def test_normalize_steam_format():
    assert q3key.normalize("ABCD-GHJL-PRST-W237") == "abcdghjlprstw237"


def test_team_arena_checksum_is_dropped():
    # Steam returns Team Arena keys with the 2-digit hex checksum from the box.
    assert q3key.normalize("ABCD-GHJL-PRST-W237-9F") == "abcdghjlprstw237"
    assert q3key.is_valid("ABCD-GHJL-PRST-W237-9F")
    # Only a hex pair is a checksum.
    assert not q3key.is_valid("ABCD-GHJL-PRST-W237-ZZ")


def test_team_arena_key_is_written_without_checksum(tmp_path):
    q3key.write(tmp_path, "missionpack", "ABCD-GHJL-PRST-W237-9F")
    assert (tmp_path / "missionpack" / "q3key").read_text()[:17] == "abcdghjlprstw237\n"


def test_valid_keys_use_the_engine_alphabet():
    assert q3key.is_valid("ABCD-GHJL-PRST-W237")
    assert not q3key.is_valid("ABCD-GHJL-PRST-W238")  # 8 is not allowed
    assert not q3key.is_valid("ABCD-EFGH-PRST-W237")  # nor E or F
    assert not q3key.is_valid("ABCD-GHJL-PRST")  # too short


def test_write_and_read(tmp_path):
    path = q3key.write(tmp_path, "baseq3", "ABCD-GHJL-PRST-W237")
    assert path == tmp_path / "baseq3" / "q3key"
    content = path.read_text()
    # The engine reads exactly the first 16 bytes.
    assert content[:16] == "abcdghjlprstw237"
    assert content[16] == "\n"
    assert q3key.read(tmp_path, "baseq3") == "abcdghjlprstw237"


def test_read_missing_or_invalid(tmp_path):
    assert q3key.read(tmp_path, "baseq3") is None
    (tmp_path / "baseq3").mkdir()
    (tmp_path / "baseq3" / "q3key").write_text("not a key at all")
    assert q3key.read(tmp_path, "baseq3") is None


def test_write_rejects_invalid(tmp_path):
    try:
        q3key.write(tmp_path, "baseq3", "nope")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid key was written")


def test_display():
    assert q3key.display("abcdghjlprstw237") == "ABCD-GHJL-PRST-W237"
