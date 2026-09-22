import hashlib
from pathlib import Path

import pytest
from sanad_ingest.fetch import HashMismatch, _cache_filename, fetch_source
from sanad_ingest.lockfile import LockedSource

RAW = "1|1|نص\n\n# Copyright (C) 2007-2026 Tanzil Project\n"
# sha256 of the verse payload "1|1|نص"
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


# --- OpenITI: the count check is against expected_records ------------------
#
# fetch_source compared `verse_count != src.expected_lines` unconditionally.
# For an openiti-markdown source expected_lines is None (its required count
# field is expected_records), so ANY integer count mismatched and the fetch
# raised every time -- the build could not run at all. The fix must not be
# "skip the check when expected_lines is None": an unchecked count is how a
# truncated download passes silently. The check moves to the count field the
# source's own format declares.

_SAMPLE = Path("tests/fixtures/bukhari_sample.txt")
_SAMPLE_RAW = _SAMPLE.read_text(encoding="utf-8")
_SAMPLE_SHA = hashlib.sha256(_SAMPLE_RAW.encode("utf-8")).hexdigest()


def _openiti_src(*, expected_records: int | None) -> LockedSource:
    return LockedSource(
        id="bukhari", kind="hadith-arabic", format="openiti-markdown",
        title="B", url="https://example.invalid/bukhari",
        license_id="public-domain", content_sha256=_SAMPLE_SHA,
        expected_records=expected_records, modifications="none")


def test_openiti_source_fetches_when_the_record_count_matches(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: _SAMPLE_RAW)
    src = _openiti_src(expected_records=10)
    assert fetch_source(src, tmp_path) == _SAMPLE_RAW


def test_openiti_record_count_mismatch_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: _SAMPLE_RAW)
    src = _openiti_src(expected_records=7129)
    with pytest.raises(HashMismatch, match="7129"):
        fetch_source(src, tmp_path)


def test_openiti_source_without_a_record_count_raises(tmp_path, monkeypatch):
    # load_lockfile already requires the field, but a LockedSource built in
    # code can still omit it. Silently skipping the check in that case is the
    # unchecked-count hole; refuse instead.
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: _SAMPLE_RAW)
    src = _openiti_src(expected_records=None)
    with pytest.raises(HashMismatch, match="expected_records"):
        fetch_source(src, tmp_path)
