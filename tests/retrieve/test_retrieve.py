import hashlib
from pathlib import Path

from sanad.corpus import db
from sanad.corpus.models import Record, Source
from sanad.retrieve.vector_store import connect_vectors, upsert_embeddings, EmbeddingRow
from sanad.retrieve.retrieve import retrieve


def _corpus(path):
    conn = db.connect(path, read_only=False)
    db.insert_source(conn, Source(id="s", kind="quran-arabic", title="t",
        publisher=None, edition=None, url="u", license_id="CC", license_url=None,
        attribution="a", retrieved_at="2026-01-01", upstream_sha256="x",
        modifications="none"))
    recs = [Record(id="quran:2:183", source_id="s", kind="ayah",
                   surah=2, ayah=183, text_ar="كتب عليكم الصيام",
                   text_ar_sha256="h", norm_light="كتب عليكم الصيام",
                   norm_standard="كتب عليكم الصيام",
                   norm_aggressive="كتب عليكم الصيام",
                   reference_display="Al-Baqarah 2:183")]
    db.insert_records(conn, recs)
    db.rebuild_fts(conn)
    conn.close()


def test_lexical_only_when_no_key(tmp_path):
    cpath = tmp_path / "c.db"; _corpus(cpath)
    cconn = db.connect(cpath)
    res = retrieve(cconn, None, arabic_terms=["الصيام", "صيام"],
                   question="fasting", voyage_key=None)
    assert any(h.record_id == "quran:2:183" for h in res.hits)
    assert res.reached["quran"] is True
    assert all(h.in_vector is False for h in res.hits)


def test_no_key_and_no_lexical_reach_sets_unreached_reason(tmp_path):
    cpath = tmp_path / "c.db"; _corpus(cpath)
    cconn = db.connect(cpath)
    # A non-Arabic question, no expandable terms, no vector key: reaches nothing.
    res = retrieve(cconn, None, arabic_terms=[], question="Fastenzeit",
                   voyage_key=None)
    assert res.hits == []
    assert res.reached == {"quran": False, "hadith": False}
    assert res.unreached_reason is not None
