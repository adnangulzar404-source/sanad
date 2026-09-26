from __future__ import annotations

import datetime as _dt
import hashlib
from pathlib import Path

from sanad.corpus import db
from sanad.corpus.models import FULL_VARIANT
from sanad.retrieve import voyage
from sanad.retrieve.vector_store import (
    EmbeddingRow,
    connect_vectors,
    get_embedding,
    upsert_embeddings,
)


def embed_text_for(conn, rec) -> str:
    """The exact text embedded for a record: the full printed unit.

    One vector per record over the whole printed text (spec §3.1) -- the
    FULL_VARIANT (matn + addenda rejoined) where the record has one, else
    text_ar. The primary/addendum split is a verify-time concern; topic
    retrieval wants the whole unit.
    """
    for v in db.get_record_variants(conn, rec.id):
        if v.variant == FULL_VARIANT:
            return v.text_ar
    return rec.text_ar


def run_embed(corpus_db: Path, vectors_db: Path, *, key: str,
              client=None, embed_fn=voyage.embed_texts) -> dict:
    cconn = db.connect(corpus_db, read_only=True)
    vconn = connect_vectors(vectors_db, read_only=False)

    pending: list[tuple[str, str, str]] = []  # (record_id, text, sha)
    total = skipped = 0
    for rec in db.iter_records(cconn):
        total += 1
        text = embed_text_for(cconn, rec)
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        existing = get_embedding(vconn, rec.id)
        if existing is not None and existing.text_sha256 == sha:
            skipped += 1
            continue
        pending.append((rec.id, text, sha))

    embedded = 0
    for start in range(0, len(pending), voyage.VOYAGE_MAX_BATCH):
        chunk = pending[start:start + voyage.VOYAGE_MAX_BATCH]
        vecs = embed_fn([t for _, t, _ in chunk], input_type="document",
                        key=key, client=client)
        upsert_embeddings(vconn, [
            EmbeddingRow(record_id=rid, model=voyage.VOYAGE_MODEL,
                         dim=voyage.VOYAGE_DIM, dtype=voyage.VOYAGE_DTYPE,
                         text_sha256=sha, vec=vec)
            for (rid, _t, sha), vec in zip(chunk, vecs)])
        embedded += len(chunk)

    vconn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('generated_at', ?)",
                  (_dt.datetime.now(tz=_dt.timezone.utc).isoformat(),))
    vconn.commit()
    cconn.close(); vconn.close()
    return {"embedded": embedded, "skipped": skipped, "total": total}
