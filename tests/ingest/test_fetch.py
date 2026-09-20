import pytest
from sanad_ingest.fetch import HashMismatch, _cache_filename, fetch_source
from sanad_ingest.lockfile import LockedSource

RAW = "1|1|نص\n\n# Copyright (C) 2007-2026 Tanzil Project\n"
# sha256 of the verse payload "1|1|نص"
import hashlib
GOOD = hashlib.sha256("1|1|نص".encode("utf-8")).hexdigest()


def _src(sha: str, *, format: str = "txt-2", url: str = "https://example.invalid/q") -> LockedSource:
    return LockedSource(
        id="t", kind="quran-arabic", format=format, title="T",
        url=url,
        license_id="CC-BY-3.0", content_sha256=sha, expected_lines=1,
        modifications="none")


def test_uses_cache_and_returns_raw_text(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    src = _src(GOOD)
    (cache / _cache_filename(src)).write_text(RAW, encoding="utf-8")
    monkeypatch.setattr("sanad_ingest.fetch._download",
                        lambda url: pytest.fail("must not download when cached"))
    assert fetch_source(src, cache) == RAW


def test_downloads_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: RAW)
    src = _src(GOOD)
    assert fetch_source(src, tmp_path) == RAW
    assert (tmp_path / _cache_filename(src)).is_file()


def test_hash_mismatch_raises_and_does_not_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: RAW)
    src = _src("0" * 64)
    with pytest.raises(HashMismatch, match="t"):
        fetch_source(src, tmp_path)
    assert not (tmp_path / _cache_filename(src)).exists()


def test_format_change_does_not_reuse_the_old_cache(tmp_path, monkeypatch):
    # Regression pin for Fix 6 / ruling R13: the Arabic source's id stayed
    # "t" (in real life, "tanzil-uthmani-1.1") while its export format moved
    # from txt-2 to xml. A cache keyed on id alone would hand the OLD txt-2
    # payload to the NEW xml parser. Caching under the txt-2 format must not
    # satisfy a later fetch for the same id under the xml format -- it must
    # download fresh instead of silently reusing (and mis-parsing) the stale
    # file.
    cache = tmp_path / "cache"
    cache.mkdir()
    old_src = _src(GOOD, format="txt-2")
    (cache / _cache_filename(old_src)).write_text(RAW, encoding="utf-8")

    xml_raw = "<quran><sura index='1'><aya index='1' text='نص'/></sura></quran>"
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: xml_raw)
    new_sha = hashlib.sha256("1|1|نص".encode("utf-8")).hexdigest()
    new_src = _src(new_sha, format="xml")

    assert fetch_source(new_src, cache) == xml_raw
    assert (cache / _cache_filename(new_src)).is_file()
    # The old txt-2 cache file is untouched, not overwritten or reused.
    assert (cache / _cache_filename(old_src)).read_text(encoding="utf-8") == RAW
    assert _cache_filename(old_src) != _cache_filename(new_src)


def test_cache_filename_changes_with_url_at_same_id_and_format():
    a = _src(GOOD, url="https://example.invalid/a")
    b = _src(GOOD, url="https://example.invalid/b")
    assert _cache_filename(a) != _cache_filename(b)


def test_line_count_mismatch_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: RAW)
    src = LockedSource(
        id="t", kind="quran-arabic", format="txt-2", title="T",
        url="https://example.invalid/q",
        license_id="CC-BY-3.0", content_sha256=GOOD, expected_lines=6236,
        modifications="none")
    with pytest.raises(HashMismatch, match="6236"):
        fetch_source(src, tmp_path)
