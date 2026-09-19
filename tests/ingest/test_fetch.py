import pytest
from sanad_ingest.fetch import HashMismatch, fetch_source
from sanad_ingest.lockfile import LockedSource

RAW = "1|1|نص\n\n# Copyright (C) 2007-2026 Tanzil Project\n"
# sha256 of the verse payload "1|1|نص"
import hashlib
GOOD = hashlib.sha256("1|1|نص".encode("utf-8")).hexdigest()


def _src(sha: str) -> LockedSource:
    return LockedSource(
        id="t", kind="quran-arabic", format="txt-2", title="T",
        url="https://example.invalid/q",
        license_id="CC-BY-3.0", content_sha256=sha, expected_lines=1,
        modifications="none")


def test_uses_cache_and_returns_raw_text(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "t.txt").write_text(RAW, encoding="utf-8")
    monkeypatch.setattr("sanad_ingest.fetch._download",
                        lambda url: pytest.fail("must not download when cached"))
    assert fetch_source(_src(GOOD), cache) == RAW


def test_downloads_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: RAW)
    assert fetch_source(_src(GOOD), tmp_path) == RAW
    assert (tmp_path / "t.txt").is_file()


def test_hash_mismatch_raises_and_does_not_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: RAW)
    with pytest.raises(HashMismatch, match="t"):
        fetch_source(_src("0" * 64), tmp_path)
    assert not (tmp_path / "t.txt").exists()


def test_line_count_mismatch_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: RAW)
    src = LockedSource(
        id="t", kind="quran-arabic", format="txt-2", title="T",
        url="https://example.invalid/q",
        license_id="CC-BY-3.0", content_sha256=GOOD, expected_lines=6236,
        modifications="none")
    with pytest.raises(HashMismatch, match="6236"):
        fetch_source(src, tmp_path)
