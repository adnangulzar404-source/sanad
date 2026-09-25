from pathlib import Path
from sanad.retrieve.vector_store import (
    EmbeddingRow, connect_vectors, upsert_embeddings, get_embedding,
    iter_embeddings, vectors_meta,
)

def _row(rid, sha, vec=b"\x00" * 128):
    return EmbeddingRow(record_id=rid, model="voyage-4", dim=1024,
                        dtype="binary", text_sha256=sha, vec=vec)

def test_upsert_then_read_roundtrips(tmp_path: Path):
    conn = connect_vectors(tmp_path / "v.db", read_only=False)
    n = upsert_embeddings(conn, [_row("quran:1:1", "aa" * 32),
                                 _row("hadith:bukhari:1", "bb" * 32)])
    assert n == 2
    got = get_embedding(conn, "quran:1:1")
    assert got is not None and got.text_sha256 == "aa" * 32
    assert got.dim == 1024 and got.dtype == "binary" and len(got.vec) == 128

def test_upsert_is_idempotent_by_record_id(tmp_path: Path):
    conn = connect_vectors(tmp_path / "v.db", read_only=False)
    upsert_embeddings(conn, [_row("quran:1:1", "aa" * 32)])
    upsert_embeddings(conn, [_row("quran:1:1", "cc" * 32, vec=b"\x01" * 128)])
    got = get_embedding(conn, "quran:1:1")
    assert got.text_sha256 == "cc" * 32 and got.vec == b"\x01" * 128
    assert sum(1 for _ in iter_embeddings(conn)) == 1

def test_meta_reports_shape(tmp_path: Path):
    conn = connect_vectors(tmp_path / "v.db", read_only=False)
    upsert_embeddings(conn, [_row("quran:1:1", "aa" * 32)])
    meta = vectors_meta(conn)
    assert meta["model"] == "voyage-4" and meta["dim"] == 1024
    assert meta["dtype"] == "binary" and meta["count"] == 1
