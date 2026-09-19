import pytest
from sanad.corpus import db
from sanad.corpus.models import Record, Source

SRC = Source(
    id="tanzil-uthmani-1.1", kind="quran-arabic", title="Tanzil Uthmani",
    publisher="Tanzil Project", edition="1.1", url="https://tanzil.net/",
    license_id="CC-BY-3.0", license_url="https://tanzil.net/docs/text_license",
    attribution="# Tanzil copyright block", retrieved_at="2026-09-19",
    upstream_sha256="deadbeef", modifications="none",
)


def _rec(rid: str, surah: int, ayah: int, text: str) -> Record:
    return Record(
        id=rid, source_id=SRC.id, kind="ayah", surah=surah, ayah=ayah,
        surah_name_ar="الإخلاص", surah_name_en="Al-Ikhlas",
        text_ar=text, text_ar_sha256="x" * 64,
        norm_light=text, norm_standard=text, norm_aggressive=text,
        reference_display=f"Al-Ikhlas {surah}:{ayah}",
    )


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db", read_only=False)
    db.insert_source(c, SRC)
    db.insert_records(c, [
        _rec("quran:112:1", 112, 1, "قل هو الله احد"),
        _rec("quran:112:2", 112, 2, "الله الصمد"),
    ])
    db.rebuild_fts(c)
    return c


def test_insert_and_get_roundtrip(conn):
    got = db.get_record(conn, "quran:112:1")
    assert got is not None
    assert got.text_ar == "قل هو الله احد"
    assert got.surah == 112


def test_get_missing_record_returns_none(conn):
    assert db.get_record(conn, "quran:999:1") is None


def test_iter_records_yields_all(conn):
    assert len(list(db.iter_records(conn))) == 2


def test_fts_candidates_finds_by_token(conn):
    hits = db.fts_candidates(conn, "الصمد")
    assert [h.id for h in hits] == ["quran:112:2"]


def test_fts_candidates_tolerates_fts_metacharacters(conn):
    # a quote containing quotes or hyphens must not raise a syntax error
    assert db.fts_candidates(conn, 'قل "هو" - الله') != []


def test_fts_candidates_empty_query_returns_empty(conn):
    assert db.fts_candidates(conn, "   ") == []


def test_corpus_stats(conn):
    stats = db.corpus_stats(conn)
    assert stats["records"] == 2
    assert stats["sources"] == 1


def test_read_only_connection_rejects_writes(tmp_path):
    p = tmp_path / "ro.db"
    db.connect(p, read_only=False).close()
    c = db.connect(p, read_only=True)
    with pytest.raises(Exception):
        c.execute("CREATE TABLE nope (x)")
