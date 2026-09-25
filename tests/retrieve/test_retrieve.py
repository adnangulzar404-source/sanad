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


def _hybrid_corpus(path):
    """A Quran ayah and a hadith, both matching the lexical term, plus a
    second ayah that only the vector retriever will find."""
    conn = db.connect(path, read_only=False)
    db.insert_source(conn, Source(id="s", kind="quran-arabic", title="t",
        publisher=None, edition=None, url="u", license_id="CC", license_url=None,
        attribution="a", retrieved_at="2026-01-01", upstream_sha256="x",
        modifications="none"))
    recs = [
        Record(id="quran:2:183", source_id="s", kind="ayah",
               surah=2, ayah=183, text_ar="كتب عليكم الصيام",
               text_ar_sha256="h1", norm_light="كتب عليكم الصيام",
               norm_standard="كتب عليكم الصيام",
               norm_aggressive="كتب عليكم الصيام",
               reference_display="Al-Baqarah 2:183"),
        Record(id="hadith:1", source_id="s", kind="hadith",
               text_ar="الصيام لي وأنا أجزي به",
               text_ar_sha256="h2", norm_light="الصيام لي وأنا أجزي به",
               norm_standard="الصيام لي وأنا أجزي به",
               norm_aggressive="الصيام لي وأنا أجزي به",
               reference_display="Bukhari 1"),
        Record(id="quran:112:1", source_id="s", kind="ayah",
               surah=112, ayah=1, text_ar="قل هو الله أحد",
               text_ar_sha256="h3", norm_light="قل هو الله أحد",
               norm_standard="قل هو الله أحد",
               norm_aggressive="قل هو الله أحد",
               reference_display="Al-Ikhlas 112:1"),
    ]
    db.insert_records(conn, recs)
    db.rebuild_fts(conn)
    conn.close()


def test_hybrid_retrieval_rewards_agreement_and_reaches_hadith(tmp_path):
    cpath = tmp_path / "c.db"; _hybrid_corpus(cpath)
    vpath = tmp_path / "v.db"

    query_vec = bytes(128)                    # all-zero query vector
    vec_exact_match = bytes(128)               # Hamming distance 0 from query
    vec_close_match = bytes([1]) + bytes(127)  # Hamming distance 1 from query

    vconn = connect_vectors(vpath, read_only=False)
    upsert_embeddings(vconn, [
        # quran:2:183 also matches lexically -- this is the "agreement" record.
        EmbeddingRow(record_id="quran:2:183", model="voyage-4", dim=1024,
                     dtype="binary", text_sha256="e1", vec=vec_exact_match),
        # quran:112:1 has no lexical match at all -- vector-only.
        EmbeddingRow(record_id="quran:112:1", model="voyage-4", dim=1024,
                     dtype="binary", text_sha256="e2", vec=vec_close_match),
        # hadith:1 gets NO embedding row -- it is lexical-only.
    ])
    vconn.close()

    def _stub_embed(texts, *, input_type, key, client=None):
        assert input_type == "query"
        assert key == "test-key"
        return [query_vec for _ in texts]

    cconn = db.connect(cpath)
    vconn = connect_vectors(vpath)
    res = retrieve(cconn, vconn, arabic_terms=["الصيام"], question="fasting",
                   voyage_key="test-key", embed_fn=_stub_embed)

    # A hit came through the vector path at all.
    assert any(h.in_vector for h in res.hits)

    # quran:2:183 is in BOTH lists (lexical match + exact-match vector) and
    # its combined RRF score dominates every record that is in only one list
    # -- fusion rewards agreement, not just presence.
    assert res.hits[0].record_id == "quran:2:183"
    assert res.hits[0].in_fts is True
    assert res.hits[0].in_vector is True

    # hadith:1 is lexical-only (no embedding was ever stored for it) and
    # still reaches the caller -- closes the symmetric §3.6 gap for hadith.
    assert any(h.record_id == "hadith:1" for h in res.hits)
    assert res.reached["hadith"] is True
