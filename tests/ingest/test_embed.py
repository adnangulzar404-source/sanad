import hashlib
from pathlib import Path

from sanad.corpus import db
from sanad.corpus.models import FULL_VARIANT, Record, RecordVariant, Source
from sanad.retrieve.vector_store import connect_vectors, get_embedding, vectors_meta
from sanad_ingest.embed import run_embed


def _mini_corpus(path: Path):
    conn = db.connect(path, read_only=False)
    db.insert_source(conn, Source(
        id="s", kind="quran-arabic", title="t", publisher=None, edition=None,
        url="u", license_id="CC", license_url=None, attribution="a",
        retrieved_at="2026-01-01", upstream_sha256="x", modifications="none"))
    recs = []
    for rid, txt in (("quran:1:1", "abc"), ("quran:1:2", "def")):
        recs.append(Record(
            id=rid, source_id="s", kind="ayah", text_ar=txt,
            text_ar_sha256=hashlib.sha256(txt.encode()).hexdigest(),
            norm_light=txt, norm_standard=txt, norm_aggressive=txt,
            reference_display=rid))
    db.insert_records(conn, recs)
    conn.close()


def _fake_embed(texts, *, input_type, key, client=None):
    return [bytes([len(t) % 256]) + bytes(127) for t in texts]


def test_embeds_every_record_first_run(tmp_path):
    cpath, vpath = tmp_path / "c.db", tmp_path / "v.db"
    _mini_corpus(cpath)
    stats = run_embed(cpath, vpath, key="k", embed_fn=_fake_embed)
    assert stats == {"embedded": 2, "skipped": 0, "total": 2}
    vconn = connect_vectors(vpath)
    assert get_embedding(vconn, "quran:1:1") is not None
    assert vectors_meta(vconn)["count"] == 2


def test_second_run_skips_unchanged_records(tmp_path):
    cpath, vpath = tmp_path / "c.db", tmp_path / "v.db"
    _mini_corpus(cpath)
    run_embed(cpath, vpath, key="k", embed_fn=_fake_embed)
    stats = run_embed(cpath, vpath, key="k", embed_fn=_fake_embed)
    assert stats == {"embedded": 0, "skipped": 2, "total": 2}


def test_changed_text_is_reembedded(tmp_path):
    cpath, vpath = tmp_path / "c.db", tmp_path / "v.db"
    _mini_corpus(cpath)
    run_embed(cpath, vpath, key="k", embed_fn=_fake_embed)
    # mutate one record's text + hash, rebuild-style, and re-embed
    conn = db.connect(cpath, read_only=False)
    conn.execute("UPDATE records SET text_ar='abcd', "
                 "text_ar_sha256=? WHERE id='quran:1:1'",
                 (hashlib.sha256(b'abcd').hexdigest(),))
    conn.commit(); conn.close()
    stats = run_embed(cpath, vpath, key="k", embed_fn=_fake_embed)
    assert stats == {"embedded": 1, "skipped": 1, "total": 2}


def test_full_variant_text_is_embedded_not_primary(tmp_path):
    # A record with a FULL_VARIANT row (matn + addenda rejoined) must be
    # hashed/embedded on that full printed text, never on the bare primary
    # `text_ar` -- embed_text_for's whole job is picking the right one.
    cpath, vpath = tmp_path / "c.db", tmp_path / "v.db"
    _mini_corpus(cpath)
    full_text = "abc plus addendum"
    conn = db.connect(cpath, read_only=False)
    db.insert_record_variants(conn, [RecordVariant(
        record_id="quran:1:1", variant=FULL_VARIANT, text_ar=full_text,
        norm_light=full_text, norm_standard=full_text,
        norm_aggressive=full_text)])
    conn.close()

    run_embed(cpath, vpath, key="k", embed_fn=_fake_embed)

    vconn = connect_vectors(vpath)
    row = get_embedding(vconn, "quran:1:1")
    assert row.text_sha256 == hashlib.sha256(full_text.encode()).hexdigest()
