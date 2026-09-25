# Stage B — Ask Pipeline Implementation Plan (backend)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `POST /api/ask` — a seven-stage evidence-brief pipeline that answers an open question with verbatim passages already in the corpus, where Claude only ever selects record IDs and writes prose (never Arabic), the server renders every quotation from the database by ID, and stage progress streams over SSE.

**Architecture:** Four deterministic stages reuse Stage A directly (router wraps `verify.claims.route_risk`; retrieval fuses the existing FTS5 `db.fts_records` with a new brute-force binary-vector search; guards and adjudication are new but small and rule-based). Three stages call Claude over raw HTTP (query expansion, select-and-frame, audit). Embeddings live in a **sidecar** database `data/sanad-vectors.db`, content-addressed so a corpus rebuild does not force a re-embed. Both HTTP clients use `httpx`, already a core dependency, so the base install stays clone-and-run with no key and no new dependency.

**Tech Stack:** FastAPI (`StreamingResponse`, SSE), `httpx` (Claude + Voyage, raw HTTP — no SDK), SQLite (sidecar vectors DB), pure-Python Hamming top-k (`int.bit_count()`), Claude `claude-opus-5` with adaptive thinking and `output_config.format` structured output.

**Spec:** `docs/superpowers/specs/2026-09-24-ask-pipeline-design.md` — the plan argues from it and travels with it. Read both.

**Scope:** Backend only. The frontend (`Ask.tsx`, `PipelineTrace`, `EvidenceBrief`, `AskComposer`, and the `<mark title>` accessibility fix from spec §8) is a **separate plan**, for the same reason Stage A and Stage C were split: each plan must produce independently testable software, and the API contract this plan freezes is what the frontend plan builds against.

## Two deliberate departures from the approved spec

Both were established by measurement during planning, before any code existed. The spec is authoritative except where this section overrides it; a future reader must not "fix" the plan back toward the spec's text on these two points.

1. **Embeddings live in a sidecar DB, not a `dtype` column on the corpus `embeddings` table (overrides spec §3.2).** `build.build_corpus` calls `out_db.unlink()` at the very start of every run (`ingest/sanad_ingest/build.py:317-318`). Every routine rebuild — each future Stage A3 collection triggers one — would destroy embeddings stored in the corpus file, forcing a Voyage-keyed re-embed as part of `sanad-ingest build`, which the spec itself (§3.3) requires to need no key. **Ruling:** a sidecar `data/sanad-vectors.db` with one `embeddings` table, rows keyed by `record_id` and content-addressed by `text_sha256` (the sha256 of the exact embedded text), so re-embedding after a rebuild is a no-op for every record whose text is unchanged. This is also cheaper: no corpus-schema migration, none of the ~53-test churn a corpus schema change causes (see spec §3.2 and `sanad-project-state`), and no change to the corpus-size ceiling accounting. The existing empty `embeddings` table in the corpus schema is left untouched and unused; do not add `dtype` to it.

2. **Stage 1 must emit multiple morphological surface forms per concept, not one Arabic term per topic (overrides the phrasing in spec §2's stage-1 row).** FTS5's `unicode61 remove_diacritics 2` tokenizer does no Arabic stemming, and the normalization tiers never strip the definite article `ال`. Measured against the shipped corpus: `صابرين` (a real word in Qur'an 3:200, `وَصَابِرُوا`) returns **zero** FTS hits; `الصبر` and `صبر` return 8 and 10 hits and are *different, non-overlapping sets*. A single well-chosen Arabic term reads as if it should be enough and is not. `retrieve`'s FTS fan-out already unions across every term in the list (see Task 4), so this is a **prompting** requirement (Task 6), not new retrieval code — but it would ship silently wrong if the stage-1 prompt asked for one term per concept.

## Global Constraints

Every task's requirements implicitly include this section. Values are copied verbatim from the spec.

- **Seven stages, in order:** 0 Router (deterministic) → 1 Query expansion (Claude) → 2 Retrieve (deterministic) → 3 Select & frame (Claude) → 4 Check (deterministic) → 5 Audit (Claude, fresh context) → 6 Adjudicate (deterministic). `PERSONAL_RULING` / `HIGH_RISK` at stage 0 → handoff packet, **no later stage runs**. `DISPUTED` and `GENERAL` proceed; `DISPUTED` carries its label through to the response.
- **Claude never emits Arabic.** It selects `record_id`s and writes prose (summary + per-item framing). The server renders every quotation from the DB by ID. This is the §1 safety property and it is structural, not policed.
- **Model `claude-opus-5`** for query expansion, select-and-frame, and audit.
- **Adaptive thinking on every Claude call:** `"thinking": {"type": "adaptive"}`. Do **not** send `budget_tokens` — it is rejected with a 400 on `claude-opus-5`. Effort via `"output_config": {"effort": "high"}`.
- **Structured output** via `"output_config": {"format": {"type": "json_schema", "schema": {...}}}` — never the deprecated `output_format`. Every schema uses `"additionalProperties": false` and a full `"required"` list. The first `text` block of the response is guaranteed valid JSON against the schema.
- **No assistant prefill** — rejected with a 400 on `claude-opus-5`. Shape the output with the schema and the system prompt, never a prefilled assistant turn.
- **Raw HTTP via `httpx`** for both Claude and Voyage. No `anthropic` SDK, no `voyageai` SDK, no OpenAI-compatible shim. Headers for Claude: `x-api-key`, `anthropic-version: 2023-06-01`, `content-type: application/json`.
- **The auditor is context-isolated:** it receives only the brief (summary + framings) and the evidence records, never stage 3's prompt or reasoning.
- **Exactly one retry.** A stage-4 block or a stage-5 overreach verdict re-runs stage 3 once, with the specific failures fed back, then abstains. No loops.
- **Abstention is a success state**, reported and counted, never an error.
- **The corpus evidence block precedes the volatile question** in every prompt and carries `"cache_control": {"type": "ephemeral"}` so the prefix caches across requests. Verify with `usage.cache_read_input_tokens`.
- **Vectors are binary-quantized, 1024 dims, 128 bytes/record** (`voyage-4`, `output_dtype: "binary"`). ~1.7 MB for 13,365 records.
- **The base package stays clone-and-run with no key and no model** (spec §7). `httpx` is already core; nothing new is added to `[project.dependencies]`. Verify (`/api/verify`, `/records`, `/search`, `/corpus`, `/health`) never touches a key or the vectors DB.
- **The question text and the search terms derived from it are never written to the audit log** (spec §9) — same rule as `/api/verify`.
- **Length bounds are contract, enforced by stage 4:** `summary` ≤ 80 words, each `framing` ≤ 25 words.

## Review Focus

Input classes the spec implies but no single task's happy path exercises, most likely to bite first. Each has its pinning test added to the owning task.

- **A German/Spanish question with no Voyage key.** Spec §3.6's last row: retrieval reaches nothing, and the response must say so (`reached` both false, `unreached_reason` set) rather than return a thin brief that reads like an answer. Pinned in Task 4 and Task 10.
- **Claude returns a `record_id` that is not in the candidate set** (hallucinated or real-but-unretrieved). Stage 4's airtight guard must block it. Pinned in Task 8.
- **Claude puts an Arabic codepoint in a framing or summary.** The structural fabrication guard must block any Arabic character. Pinned in Task 8, including a framing that is Arabic-adjacent (a transliterated narrator name) which must **pass**.
- **A framing that legitimately cites "Sahih al-Bukhari 2866" or names "al-Ḥasan al-Baṣrī."** The grading guard must not block either — a guard that suppresses correct output fails as hard as one that admits wrong output (spec §5, §10). Pinned in Task 8 and Task 12.
- **Claude returns `stop_reason: "refusal"` or malformed JSON / HTTP error.** A model stage failing is not a 500 — it degrades to abstention with a reason. Pinned in Task 5 and Task 10.

---

## File structure

```
api/sanad/retrieve/
  __init__.py
  vector_store.py     sidecar DB: schema, connect, read/write embeddings
  voyage.py           Voyage HTTP embed + pure-Python Hamming top-k + key resolution
  fuse.py             reciprocal-rank fusion
  retrieve.py         Stage 2: FTS5 (db.fts_records) + vector search, fused; reachability
api/sanad/agents/
  __init__.py
  claude_client.py    shared Claude HTTP call (structured output) + key resolution + refusal/error handling
  expand.py           Stage 1: query expansion
  select.py           Stage 3: select & frame
  audit.py            Stage 5: audit (fresh context)
api/sanad/pipeline/
  __init__.py
  types.py            shared dataclasses used across stages (kept in one place so every stage agrees on names/fields)
  guards.py           Stage 4: the deterministic checks
  adjudicate.py       Stage 6: publish / relabel / retry / abstain
  orchestrate.py      Stage 0 router + the seven-stage loop, emits StageEvents
api/sanad/api/
  routes.py           MODIFY: add POST /api/ask (SSE)
  schemas.py          MODIFY: AskRequest, AskFinal, item/reached models
  engine.py           MODIFY (verify/): R46 also_at/contained_in split
ingest/sanad_ingest/
  embed.py            `sanad-ingest embed`: generate vectors into the sidecar DB
  cli.py              MODIFY: register the `embed` subcommand
eval/
  cases/ask/          adversarial stage-3 fixtures (JSON) + recorded responses
  ask_runner.py       the Ask gate (stage-4 adversarial suite)
```

`api/sanad/pipeline/types.py` holds the dataclasses that cross stage boundaries, so a name or field defined once is imported everywhere rather than re-declared. The types and their exact fields:

```python
# api/sanad/pipeline/types.py — the shared vocabulary. Defined in Task 4/6/7/8/9
# as each stage's task lands; collected here so every task imports the same names.
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True)
class RetrievalHit:
    record_id: str
    rrf_score: float
    in_fts: bool
    in_vector: bool

@dataclass(frozen=True)
class RetrievalResult:
    hits: list[RetrievalHit]              # fused, truncated to RETRIEVAL_TOP_K, best first
    reached: dict[str, bool]              # {"quran": bool, "hadith": bool}
    unreached_reason: str | None
    candidate_count: int

@dataclass(frozen=True)
class Expansion:
    question_language: str                # ISO 639-1
    search_terms: list[str]               # Arabic surface forms, multiple per concept

@dataclass(frozen=True)
class SelectedItem:
    record_id: str
    framing: str

@dataclass(frozen=True)
class Selection:
    summary: str
    items: list[SelectedItem]

@dataclass(frozen=True)
class GuardResult:
    name: str
    passed: bool
    detail: str

@dataclass(frozen=True)
class AuditVerdict:
    overreach: bool
    flags: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class StageEvent:
    stage: str                            # "router"|"expand"|"retrieve"|"select"|"check"|"audit"|"final"|"error"
    payload: dict
```

---

## Task 1: Vector sidecar store

**Files:**
- Create: `api/sanad/retrieve/__init__.py` (empty)
- Create: `api/sanad/retrieve/vector_store.py`
- Test: `tests/retrieve/test_vector_store.py`

**Interfaces:**
- Produces:
  - `VECTORS_SCHEMA_SQL: str`
  - `connect_vectors(path, *, read_only=True) -> sqlite3.Connection`
  - `upsert_embeddings(conn, rows: Iterable[EmbeddingRow]) -> int`
  - `get_embedding(conn, record_id: str) -> EmbeddingRow | None`
  - `iter_embeddings(conn) -> Iterator[EmbeddingRow]` (yields `record_id, text_sha256, vec` for every row)
  - `EmbeddingRow` dataclass: `record_id: str, model: str, dim: int, dtype: str, text_sha256: str, vec: bytes`
  - `vectors_meta(conn) -> dict` (`{"model", "dim", "dtype", "count", "generated_at"}` from a one-row `meta` table)

**Why a sidecar with `text_sha256`:** see "Two deliberate departures" #1. The content hash is what makes re-embedding idempotent across corpus rebuilds.

- [ ] **Step 1: Write the failing test**

```python
# tests/retrieve/test_vector_store.py
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
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `pytest tests/retrieve/test_vector_store.py -v`
Expected: FAIL — `ModuleNotFoundError: sanad.retrieve.vector_store`.

- [ ] **Step 3: Write the minimal implementation**

```python
# api/sanad/retrieve/vector_store.py
from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

# Content-addressed embeddings, in their OWN database file, never the corpus DB.
# build_corpus() unlinks the corpus file on every run; keeping vectors here means
# a rebuild does not destroy them and re-embedding is idempotent by text_sha256.
VECTORS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS embeddings (
  record_id    TEXT PRIMARY KEY,
  model        TEXT NOT NULL,
  dim          INTEGER NOT NULL,
  dtype        TEXT NOT NULL,
  text_sha256  TEXT NOT NULL,
  vec          BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class EmbeddingRow:
    record_id: str
    model: str
    dim: int
    dtype: str
    text_sha256: str
    vec: bytes


_COLS = ("record_id", "model", "dim", "dtype", "text_sha256", "vec")


def connect_vectors(path: str | Path, *, read_only: bool = True) -> sqlite3.Connection:
    path = Path(path)
    if read_only:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.executescript(VECTORS_SCHEMA_SQL)
    conn.row_factory = sqlite3.Row
    return conn


def upsert_embeddings(conn: sqlite3.Connection, rows: Iterable[EmbeddingRow]) -> int:
    data = [tuple(getattr(r, c) for c in _COLS) for r in rows]
    conn.executemany(
        f"INSERT OR REPLACE INTO embeddings ({','.join(_COLS)}) "
        f"VALUES ({','.join('?' * len(_COLS))})", data)
    conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('count', ?)",
                 (str(conn.execute("SELECT count(*) FROM embeddings").fetchone()[0]),))
    if data:
        conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('model', ?)", (data[0][1],))
        conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('dim', ?)", (str(data[0][2]),))
        conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('dtype', ?)", (data[0][3],))
    conn.commit()
    return len(data)


def _to_row(r: sqlite3.Row) -> EmbeddingRow:
    return EmbeddingRow(**{c: r[c] for c in _COLS})


def get_embedding(conn: sqlite3.Connection, record_id: str) -> EmbeddingRow | None:
    r = conn.execute(
        f"SELECT {','.join(_COLS)} FROM embeddings WHERE record_id = ?",
        (record_id,)).fetchone()
    return _to_row(r) if r else None


def iter_embeddings(conn: sqlite3.Connection) -> Iterator[EmbeddingRow]:
    for r in conn.execute(f"SELECT {','.join(_COLS)} FROM embeddings ORDER BY record_id"):
        yield _to_row(r)


def vectors_meta(conn: sqlite3.Connection) -> dict:
    rows = {r["k"]: r["v"] for r in conn.execute("SELECT k, v FROM meta")}
    return {
        "model": rows.get("model"),
        "dim": int(rows["dim"]) if "dim" in rows else None,
        "dtype": rows.get("dtype"),
        "count": int(rows.get("count", 0)),
        "generated_at": rows.get("generated_at"),
    }
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `pytest tests/retrieve/test_vector_store.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add api/sanad/retrieve/__init__.py api/sanad/retrieve/vector_store.py tests/retrieve/test_vector_store.py
git commit -m "feat(retrieve): content-addressed vector sidecar store"
```

---

## Task 2: Voyage embed client + Hamming top-k

**Files:**
- Create: `api/sanad/retrieve/voyage.py`
- Test: `tests/retrieve/test_voyage.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `resolve_voyage_key() -> str | None` (env `VOYAGE_API_KEY`, else None)
  - `embed_texts(texts: list[str], *, input_type: str, key: str, client: httpx.Client | None = None) -> list[bytes]` — one 128-byte binary vector per text, in order. `input_type` is `"document"` or `"query"`.
  - `hamming_topk(query: bytes, corpus: list[tuple[str, bytes]], k: int) -> list[tuple[str, int]]` — `(record_id, distance)` for the k nearest, smallest distance first.
  - `VOYAGE_MODEL = "voyage-4"`, `VOYAGE_DIM = 1024`, `VOYAGE_DTYPE = "binary"`, `VOYAGE_MAX_BATCH = 1000`
  - `class VoyageError(Exception)`

**Voyage API shape (pinned from published docs 2026-09-24, NOT yet verified live — no key exists yet).** `POST https://api.voyageai.com/v1/embeddings`, `Authorization: Bearer <key>`, body `{"input": [...], "model": "voyage-4", "output_dtype": "binary", "input_type": "..."}`. Binary vectors return as int8 arrays that pack to 128 bytes at 1024 dims. **First live smoke test once a key lands must confirm this response shape** (see Task 3 note) — if it differs, this is the one place to fix it.

- [ ] **Step 1: Write the failing test** (no network — inject a fake transport)

```python
# tests/retrieve/test_voyage.py
import httpx
from sanad.retrieve.voyage import embed_texts, hamming_topk, VoyageError

def _fake_client(payload, status=200):
    def handler(request):
        return httpx.Response(status, json=payload)
    return httpx.Client(transport=httpx.MockTransport(handler))

def test_embed_texts_packs_binary_vectors_in_order():
    # Voyage returns one 1024-bit vector per text as 128 signed int8 bytes.
    payload = {"data": [
        {"index": 0, "embedding": [1] * 128},
        {"index": 1, "embedding": [-1] * 128},
    ]}
    out = embed_texts(["a", "b"], input_type="document", key="k",
                      client=_fake_client(payload))
    assert len(out) == 2 and all(len(v) == 128 for v in out)

def test_embed_texts_reorders_by_index():
    payload = {"data": [
        {"index": 1, "embedding": [0] * 128},
        {"index": 0, "embedding": [127] * 128},
    ]}
    out = embed_texts(["first", "second"], input_type="document", key="k",
                      client=_fake_client(payload))
    assert out[0] == bytes([127] * 128) and out[1] == bytes([0] * 128)

def test_embed_texts_raises_on_http_error():
    try:
        embed_texts(["a"], input_type="document", key="k",
                    client=_fake_client({"error": "bad"}, status=401))
        assert False, "expected VoyageError"
    except VoyageError:
        pass

def test_hamming_topk_orders_by_distance():
    q = bytes([0b00000000]) + bytes(127)
    corpus = [
        ("same", bytes([0b00000000]) + bytes(127)),   # distance 0
        ("one",  bytes([0b00000001]) + bytes(127)),   # distance 1
        ("three", bytes([0b00000111]) + bytes(127)),  # distance 3
    ]
    got = hamming_topk(q, corpus, k=2)
    assert [rid for rid, _ in got] == ["same", "one"]
    assert got[0][1] == 0 and got[1][1] == 1
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `pytest tests/retrieve/test_voyage.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the minimal implementation**

```python
# api/sanad/retrieve/voyage.py
from __future__ import annotations

import os

import httpx

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-4"
VOYAGE_DIM = 1024
VOYAGE_DTYPE = "binary"
VOYAGE_MAX_BATCH = 1000
_TIMEOUT = 60.0


class VoyageError(Exception):
    pass


def resolve_voyage_key() -> str | None:
    return os.environ.get("VOYAGE_API_KEY") or None


def embed_texts(texts: list[str], *, input_type: str, key: str,
                client: httpx.Client | None = None) -> list[bytes]:
    if input_type not in ("document", "query"):
        raise ValueError(f"input_type must be 'document' or 'query', got {input_type!r}")
    owns = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        out: list[bytes] = []
        for start in range(0, len(texts), VOYAGE_MAX_BATCH):
            batch = texts[start:start + VOYAGE_MAX_BATCH]
            resp = client.post(
                VOYAGE_URL,
                headers={"Authorization": f"Bearer {key}",
                         "content-type": "application/json"},
                json={"input": batch, "model": VOYAGE_MODEL,
                      "output_dtype": VOYAGE_DTYPE, "input_type": input_type})
            if resp.status_code != 200:
                raise VoyageError(f"voyage {resp.status_code}: {resp.text[:200]}")
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            for d in data:
                # signed int8 array -> 128 bytes (two's complement)
                out.append(bytes((x & 0xFF) for x in d["embedding"]))
        return out
    except httpx.HTTPError as exc:
        raise VoyageError(str(exc)) from exc
    finally:
        if owns:
            client.close()


def hamming_topk(query: bytes, corpus: list[tuple[str, bytes]],
                 k: int) -> list[tuple[str, int]]:
    qi = int.from_bytes(query, "big")
    scored = [(rid, (qi ^ int.from_bytes(vec, "big")).bit_count())
              for rid, vec in corpus]
    scored.sort(key=lambda t: (t[1], t[0]))
    return scored[:k]
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `pytest tests/retrieve/test_voyage.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add api/sanad/retrieve/voyage.py tests/retrieve/test_voyage.py
git commit -m "feat(retrieve): Voyage binary-embed client and pure-Python Hamming top-k"
```

---

## Task 3: `sanad-ingest embed` CLI

**Files:**
- Create: `ingest/sanad_ingest/embed.py`
- Modify: `ingest/sanad_ingest/cli.py` (register the subcommand)
- Test: `tests/ingest/test_embed.py`

**Interfaces:**
- Consumes: `vector_store.{connect_vectors,upsert_embeddings,get_embedding,EmbeddingRow}` (Task 1); `voyage.{embed_texts,resolve_voyage_key,VOYAGE_MODEL,VOYAGE_DIM,VOYAGE_DTYPE}` (Task 2); `corpus.db.{connect,iter_records}`.
- Produces:
  - `embed_text_for(rec) -> str` — the exact text embedded for a record: the record's `FULL_VARIANT` text where one exists (rejoined printed hadith), else `text_ar`. **One vector per record, over the full printed unit** (spec §3.1).
  - `run_embed(corpus_db, vectors_db, *, key, client=None, embed_fn=embed_texts) -> dict` — embeds only records whose `text_sha256` is absent or changed in the sidecar; returns `{"embedded": n, "skipped": n, "total": n}`.
  - CLI: `sanad-ingest embed --db data/sanad-quran.db --vectors data/sanad-vectors.db`

**Idempotence is the point:** a record is re-embedded only when `sha256(embed_text_for(rec))` differs from the sidecar row's `text_sha256`. After a corpus rebuild that changed nothing, `embedded == 0`.

**embed_text_for and FULL_VARIANT:** the rejoined printed text lives in `record_variants` (`variant='full'`), not on the `Record`. `run_embed` reads it via `db.get_record_variants(conn, rec.id)` and picks the `FULL_VARIANT` row's `text_ar` when present.

- [ ] **Step 1: Write the failing test** (fake embed_fn, real SQLite)

```python
# tests/ingest/test_embed.py
import hashlib
from pathlib import Path

from sanad.corpus import db
from sanad.corpus.models import Record, Source
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
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `pytest tests/ingest/test_embed.py -v`
Expected: FAIL — `sanad_ingest.embed` missing.

- [ ] **Step 3: Write the minimal implementation**

```python
# ingest/sanad_ingest/embed.py
from __future__ import annotations

import datetime as _dt
import hashlib
from pathlib import Path

from sanad.corpus import db
from sanad.corpus.models import FULL_VARIANT
from sanad.retrieve import voyage
from sanad.retrieve.vector_store import (
    EmbeddingRow, connect_vectors, get_embedding, upsert_embeddings,
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
```

Then wire the subcommand into `cli.py`:

```python
# ingest/sanad_ingest/cli.py — inside main(), after the build subparser
    e = sub.add_parser("embed", help="generate embeddings into the vectors sidecar DB")
    e.add_argument("--db", type=Path, default=Path("data/sanad-quran.db"))
    e.add_argument("--vectors", type=Path, default=Path("data/sanad-vectors.db"))
    e.add_argument("-v", "--verbose", action="store_true")

# ...after args = parser.parse_args(argv) and logging setup, branch on command:
    if args.command == "embed":
        from .embed import run_embed
        from sanad.retrieve.voyage import resolve_voyage_key
        key = resolve_voyage_key()
        if not key:
            print("error: VOYAGE_API_KEY is not set; embedding needs a Voyage key. "
                  "The rest of the corpus builds and serves without one.",
                  file=sys.stderr)
            return 1
        stats = run_embed(args.db, args.vectors, key=key)
        print(f"embedded {stats['embedded']}, skipped {stats['skipped']} "
              f"(total {stats['total']}) -> {args.vectors}")
        return 0
```

> The existing `build` path stays exactly as it is: `build_corpus(...)` runs only when `args.command == "build"`. Restructure `main()` so the build-specific tail (the `hashlib.sha256(args.out.read_bytes())` print) runs only under the build branch.

- [ ] **Step 4: Run the tests, confirm they pass**

Run: `pytest tests/ingest/test_embed.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Live smoke test (manual, once a Voyage key exists — NOT in CI)**

Run: `VOYAGE_API_KEY=... sanad-ingest embed --db data/sanad-quran.db --vectors /tmp/v.db`
Expected: `embedded 13365, skipped 0`. **This is the first verification of the Voyage response shape pinned in Task 2** — if the response is not `{"data":[{"index","embedding"}]}` with a 128-int array, fix `voyage.embed_texts` here. Record the outcome; do not commit `data/sanad-vectors.db` from this scratch run.

- [ ] **Step 6: Commit**

```bash
git add ingest/sanad_ingest/embed.py ingest/sanad_ingest/cli.py tests/ingest/test_embed.py
git commit -m "feat(ingest): sanad-ingest embed, idempotent by content hash"
```

---

## Task 4: Retrieval — RRF fusion + orchestration

**Files:**
- Create: `api/sanad/pipeline/__init__.py` (empty), `api/sanad/pipeline/types.py` (the dataclasses above)
- Create: `api/sanad/retrieve/fuse.py`, `api/sanad/retrieve/retrieve.py`
- Test: `tests/retrieve/test_fuse.py`, `tests/retrieve/test_retrieve.py`

**Interfaces:**
- Consumes: `vector_store.{connect_vectors,iter_embeddings}` (Task 1); `voyage.{embed_texts,hamming_topk,resolve_voyage_key}` (Task 2); `corpus.db.{fts_records,get_record}`; `pipeline.types.{RetrievalHit,RetrievalResult}`.
- Produces:
  - `rrf_fuse(ranked_lists: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]` — reciprocal-rank fusion, best first.
  - `RETRIEVAL_K_PER_RETRIEVER = 50`, `RETRIEVAL_TOP_K = 24`
  - `retrieve(corpus_conn, vectors_conn, *, arabic_terms, question, voyage_key, embed_fn=embed_texts) -> RetrievalResult`

**RRF, not weighted sum** (spec §3.4): the lexical and vector lists are on incomparable scales, and RRF needs no calibration. **Depth k=50 per retriever, fused and truncated to top 24** (measured: deepest first-relevant hit across 8 realistic topical questions was rank 11 — Al-Baqarah 2:183 for "fasting" — so 24 gives >2× margin; see `sanad-ask-pipeline-plan-progress`).

**Reachability (spec §3.6):** `reached["quran"]` / `reached["hadith"]` is true when at least one fused hit is of that kind. `unreached_reason` is set when the vector retriever could not run (no key or empty sidecar) AND lexical retrieval reached nothing for the question — the German/Spanish-with-no-key case from Review Focus. FTS fans out across **every** term in `arabic_terms`, unioned (this is why Task 6's prompt must supply multiple surface forms).

- [ ] **Step 1: Write the failing test for fusion**

```python
# tests/retrieve/test_fuse.py
from sanad.retrieve.fuse import rrf_fuse

def test_rrf_rewards_agreement_across_lists():
    lexical = ["a", "b", "c"]
    vector = ["b", "a", "d"]
    fused = [rid for rid, _ in rrf_fuse([lexical, vector])]
    # b and a appear high in both; they lead. d and c appear in one each.
    assert fused[:2] == ["a", "b"] or fused[:2] == ["b", "a"]
    assert set(fused) == {"a", "b", "c", "d"}

def test_rrf_single_list_preserves_order():
    assert [r for r, _ in rrf_fuse([["x", "y", "z"]])] == ["x", "y", "z"]

def test_rrf_empty_input_is_empty():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []
```

- [ ] **Step 2: Run, confirm fail** — `pytest tests/retrieve/test_fuse.py -v` → module missing.

- [ ] **Step 3: Implement fusion**

```python
# api/sanad/retrieve/fuse.py
from __future__ import annotations


def rrf_fuse(ranked_lists: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal-rank fusion. Score = sum over lists of 1/(k + rank), rank 0-based.

    k=60 is the conventional RRF constant; it damps the contribution of deep
    ranks so a top-1 in one list is not overwhelmed by a long tail in another.
    """
    scores: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, rid in enumerate(lst):
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda t: (-t[1], t[0]))
```

- [ ] **Step 4: Run, confirm pass.**

- [ ] **Step 5: Write the failing test for orchestration**

```python
# tests/retrieve/test_retrieve.py
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
```

- [ ] **Step 6: Run, confirm fail.**

- [ ] **Step 7: Implement orchestration**

```python
# api/sanad/retrieve/retrieve.py
from __future__ import annotations

import sqlite3

from ..corpus import db
from ..pipeline.types import RetrievalHit, RetrievalResult
from . import voyage
from .fuse import rrf_fuse
from .vector_store import iter_embeddings

RETRIEVAL_K_PER_RETRIEVER = 50
RETRIEVAL_TOP_K = 24

_NO_REACH = ("Retrieval could not reach the corpus for this question: no Arabic "
             "search terms were available and vector search is unavailable "
             "(no Voyage key or no embeddings). Ask cannot answer without "
             "reaching the corpus, and does not guess.")


def _fts_ranked(conn: sqlite3.Connection, arabic_terms: list[str]) -> list[str]:
    """Union FTS results across every surface form, best-ranked first, deduped.

    FTS5 has no Arabic stemmer and the norms never strip `ال`, so one term is
    not enough (see plan §departures 2). Every term is queried; a record's best
    (earliest) appearance across terms sets its rank.
    """
    seen: dict[str, int] = {}
    order: list[str] = []
    for term in arabic_terms:
        for rec in db.fts_records(conn, term, RETRIEVAL_K_PER_RETRIEVER):
            if rec.id not in seen:
                seen[rec.id] = len(order)
                order.append(rec.id)
    return order


def _vector_ranked(cconn, vconn, *, question, key, embed_fn) -> list[str]:
    if vconn is None or not key:
        return []
    corpus = [(e.record_id, e.vec) for e in iter_embeddings(vconn)]
    if not corpus:
        return []
    qvec = embed_fn([question], input_type="query", key=key)[0]
    return [rid for rid, _dist in
            voyage.hamming_topk(qvec, corpus, RETRIEVAL_K_PER_RETRIEVER)]


def retrieve(corpus_conn, vectors_conn, *, arabic_terms, question,
             voyage_key, embed_fn=voyage.embed_texts) -> RetrievalResult:
    lexical = _fts_ranked(corpus_conn, arabic_terms)
    try:
        vector = _vector_ranked(corpus_conn, vectors_conn, question=question,
                                key=voyage_key, embed_fn=embed_fn)
    except voyage.VoyageError:
        vector = []  # degrade to lexical; never fail the whole request

    fused = rrf_fuse([lexical, vector])[:RETRIEVAL_TOP_K]
    lex_set, vec_set = set(lexical), set(vector)
    hits: list[RetrievalHit] = []
    reached = {"quran": False, "hadith": False}
    for rid, score in fused:
        rec = db.get_record(corpus_conn, rid)
        if rec is None:
            continue
        hits.append(RetrievalHit(record_id=rid, rrf_score=score,
                                 in_fts=rid in lex_set, in_vector=rid in vec_set))
        reached[rec.kind if rec.kind == "hadith" else "quran"] = True

    unreached = _NO_REACH if not hits and not vector and not lexical else None
    return RetrievalResult(hits=hits, reached=reached,
                           unreached_reason=unreached, candidate_count=len(hits))
```

- [ ] **Step 8: Run both retrieval test files, confirm pass**

Run: `pytest tests/retrieve/ -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add api/sanad/pipeline/__init__.py api/sanad/pipeline/types.py \
        api/sanad/retrieve/fuse.py api/sanad/retrieve/retrieve.py \
        tests/retrieve/test_fuse.py tests/retrieve/test_retrieve.py
git commit -m "feat(retrieve): RRF fusion and hybrid retrieval with reachability"
```

---
## Task 5: Claude HTTP client (structured output) + key resolution

**Files:**
- Create: `api/sanad/agents/__init__.py` (empty), `api/sanad/agents/claude_client.py`
- Test: `tests/agents/test_claude_client.py`

**Interfaces:**
- Produces:
  - `resolve_anthropic_key() -> str | None` (env `ANTHROPIC_API_KEY`)
  - `CLAUDE_MODEL = "claude-opus-5"`, `ANTHROPIC_URL`, `ANTHROPIC_VERSION = "2023-06-01"`
  - `class ClaudeError(Exception)` — every model-stage failure (HTTP error, refusal, malformed JSON) raises this. Callers turn it into abstention, never a 500.
  - `call_structured(*, system_blocks, user_text, schema, key, effort="high", client=None) -> dict` — one Messages call with adaptive thinking and `output_config.format`; returns the parsed JSON dict from the first text block. `system_blocks` is a list of content blocks so the caller controls `cache_control` placement.

**Why module-qualified imports matter (carried forward from the stale draft's self-review):** stages 1/3/5 must call `claude_client.call_structured(...)` via `from . import claude_client`, NOT `from .claude_client import call_structured`. The eval runner (Task 12) monkeypatches `claude_client.call_structured`; a name imported into the stage module's namespace would not be intercepted. Apply this in Tasks 6, 7, 9.

**Refusal and errors (Review Focus):** `stop_reason == "refusal"` returns HTTP 200 — check it before reading content and raise `ClaudeError`. Any non-200, any missing text block, any `json.loads` failure → `ClaudeError`.

- [ ] **Step 1: Write the failing test** (fake transport)

```python
# tests/agents/test_claude_client.py
import httpx
from sanad.agents.claude_client import call_structured, ClaudeError

_SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}},
           "required": ["x"], "additionalProperties": False}

def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))

def test_returns_parsed_json_from_first_text_block():
    def h(req):
        return httpx.Response(200, json={
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": '{"x": "ok"}'}],
            "usage": {"cache_read_input_tokens": 0}})
    out = call_structured(system_blocks=[{"type": "text", "text": "sys"}],
                          user_text="q", schema=_SCHEMA, key="k", client=_client(h))
    assert out == {"x": "ok"}

def test_refusal_raises_claude_error():
    def h(req):
        return httpx.Response(200, json={"stop_reason": "refusal",
                                         "stop_details": {"category": "reasoning_extraction"},
                                         "content": []})
    try:
        call_structured(system_blocks=[{"type": "text", "text": "s"}], user_text="q",
                        schema=_SCHEMA, key="k", client=_client(h))
        assert False
    except ClaudeError:
        pass

def test_http_error_raises_claude_error():
    def h(req):
        return httpx.Response(429, json={"error": "rate"})
    try:
        call_structured(system_blocks=[{"type": "text", "text": "s"}], user_text="q",
                        schema=_SCHEMA, key="k", client=_client(h))
        assert False
    except ClaudeError:
        pass

def test_request_body_uses_adaptive_thinking_and_output_config():
    seen = {}
    def h(req):
        import json
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"stop_reason": "end_turn",
            "content": [{"type": "text", "text": '{"x":"1"}'}], "usage": {}})
    call_structured(system_blocks=[{"type": "text", "text": "s"}], user_text="q",
                    schema=_SCHEMA, key="k", client=_client(h))
    assert seen["model"] == "claude-opus-5"
    assert seen["thinking"] == {"type": "adaptive"}
    assert seen["output_config"]["format"]["type"] == "json_schema"
    assert seen["output_config"]["effort"] == "high"
    assert "budget_tokens" not in seen.get("thinking", {})
```

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement**

```python
# api/sanad/agents/claude_client.py
from __future__ import annotations

import json
import os

import httpx

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
CLAUDE_MODEL = "claude-opus-5"
_TIMEOUT = 120.0
_MAX_TOKENS = 16000


class ClaudeError(Exception):
    pass


def resolve_anthropic_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY") or None


def call_structured(*, system_blocks: list[dict], user_text: str, schema: dict,
                    key: str, effort: str = "high",
                    client: httpx.Client | None = None) -> dict:
    owns = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": _MAX_TOKENS,
        "thinking": {"type": "adaptive"},
        "output_config": {
            "effort": effort,
            "format": {"type": "json_schema", "schema": schema},
        },
        "system": system_blocks,
        "messages": [{"role": "user", "content": user_text}],
    }
    try:
        resp = client.post(ANTHROPIC_URL, headers={
            "x-api-key": key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }, json=body)
    except httpx.HTTPError as exc:
        raise ClaudeError(f"transport: {exc}") from exc
    finally:
        if owns:
            client.close()

    if resp.status_code != 200:
        raise ClaudeError(f"anthropic {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if data.get("stop_reason") == "refusal":
        cat = (data.get("stop_details") or {}).get("category")
        raise ClaudeError(f"model refused (category={cat})")
    try:
        text = next(b["text"] for b in data["content"] if b.get("type") == "text")
        return json.loads(text)
    except (StopIteration, KeyError, json.JSONDecodeError) as exc:
        raise ClaudeError(f"no valid JSON in response: {exc}") from exc
```

- [ ] **Step 4: Run, confirm pass** — `pytest tests/agents/test_claude_client.py -v`.

- [ ] **Step 5: Commit**

```bash
git add api/sanad/agents/__init__.py api/sanad/agents/claude_client.py tests/agents/test_claude_client.py
git commit -m "feat(agents): Claude structured-output client with refusal handling"
```

---

## Task 6: Stage 1 — query expansion

**Files:**
- Create: `api/sanad/agents/expand.py`
- Test: `tests/agents/test_expand.py`

**Interfaces:**
- Consumes: `agents.claude_client` (module-qualified); `pipeline.types.Expansion`.
- Produces: `expand_query(question: str, *, key: str, client=None) -> Expansion`; `EXPAND_SYSTEM: str`; `EXPAND_SCHEMA: dict`.

**The prompt must ask for multiple morphological surface forms per concept** (plan §departures 2), with a worked example, because FTS5 does no Arabic stemming and never strips `ال`. The schema: `{"question_language": str (ISO 639-1), "search_terms": [str]}`.

- [ ] **Step 1: Write the failing test** (monkeypatch the module-qualified call)

```python
# tests/agents/test_expand.py
from sanad.agents import expand
from sanad.pipeline.types import Expansion

def test_expand_returns_language_and_terms(monkeypatch):
    def fake(*, system_blocks, user_text, schema, key, effort="high", client=None):
        assert "surface form" in system_blocks[0]["text"].lower()  # prompt asks for forms
        return {"question_language": "en",
                "search_terms": ["الصبر", "صبر", "صابرين", "يصبر"]}
    monkeypatch.setattr(expand.claude_client, "call_structured", fake)
    out = expand.expand_query("How should I be patient?", key="k")
    assert isinstance(out, Expansion)
    assert out.question_language == "en"
    assert "صبر" in out.search_terms and len(out.search_terms) >= 2

def test_expand_propagates_claude_error(monkeypatch):
    from sanad.agents.claude_client import ClaudeError
    def boom(**kw): raise ClaudeError("refused")
    monkeypatch.setattr(expand.claude_client, "call_structured", boom)
    try:
        expand.expand_query("q", key="k"); assert False
    except ClaudeError:
        pass
```

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement**

```python
# api/sanad/agents/expand.py
from __future__ import annotations

from . import claude_client
from ..pipeline.types import Expansion

EXPAND_SYSTEM = (
    "You expand a user's question into Arabic search terms for a lexical index "
    "over the Qur'an and Sahih al-Bukhari. The index does NOT stem Arabic and "
    "does NOT strip the definite article. So for each concept in the question, "
    "emit SEVERAL surface forms, not one: the bare root-word, the form with "
    "the definite article ال, and common inflections (verb, active participle, "
    "plural). Example — concept 'patience' -> ['صبر', 'الصبر', 'صابرين', "
    "'يصبر', 'اصبروا']. Detect the question's language as an ISO 639-1 code. "
    "Return ONLY the structured object. Do not answer the question."
)

EXPAND_SCHEMA = {
    "type": "object",
    "properties": {
        "question_language": {"type": "string"},
        "search_terms": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["question_language", "search_terms"],
    "additionalProperties": False,
}


def expand_query(question: str, *, key: str, client=None) -> Expansion:
    data = claude_client.call_structured(
        system_blocks=[{"type": "text", "text": EXPAND_SYSTEM}],
        user_text=question, schema=EXPAND_SCHEMA, key=key, client=client)
    return Expansion(question_language=data["question_language"],
                     search_terms=list(data["search_terms"]))
```

- [ ] **Step 4: Run, confirm pass.**

- [ ] **Step 5: Commit**

```bash
git add api/sanad/agents/expand.py tests/agents/test_expand.py
git commit -m "feat(agents): stage 1 query expansion with multi-form Arabic terms"
```

---

## Task 7: Stage 3 — select & frame

**Files:**
- Create: `api/sanad/agents/select.py`
- Test: `tests/agents/test_select.py`

**Interfaces:**
- Consumes: `agents.claude_client` (module-qualified); `pipeline.types.{Selection,SelectedItem,RetrievalHit}`; `corpus.db.get_record`.
- Produces:
  - `build_evidence_block(corpus_conn, hits) -> str` — the candidates with their id, reference, and Arabic text, rendered for the prompt. This is the CACHED prefix.
  - `select_and_frame(corpus_conn, question, hits, *, key, client=None, feedback=None) -> Selection` — Claude picks relevant candidates, writes one ≤25-word framing each and a ≤80-word summary. `feedback` (the retry path) is appended to the volatile suffix.
  - `SELECT_SYSTEM: str`, `SELECT_SCHEMA: dict`.

**Prompt caching (spec §8, Global Constraints):** the evidence block goes in a **system block carrying `cache_control`**, before the volatile question. Ordering is `tools → system → messages`, so a stable system prefix caches across requests with different questions. The system content is `[{stable instructions}, {evidence block, cache_control: ephemeral}]`; the question (and any retry feedback) is the user message.

**Claude writes prose and IDs only — never Arabic.** The schema has no Arabic field; stage 4 enforces it. Framing for a hadith in a non-Arabic brief is a *labelled explanation*, never a translation (spec §4).

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_select.py
from sanad.agents import select
from sanad.pipeline.types import RetrievalHit, Selection

class _Rec:
    def __init__(self, rid, ref, text): self.id, self.reference_display, self.text_ar = rid, ref, text

def _conn_with(records):
    class C:
        def __init__(self, m): self.m = m
    import sanad.agents.select as s
    return records  # helper replaced via monkeypatch below

def test_select_builds_cached_evidence_and_parses(monkeypatch):
    recs = {"quran:2:183": _Rec("quran:2:183", "Al-Baqarah 2:183", "كتب عليكم الصيام")}
    monkeypatch.setattr(select.db, "get_record", lambda c, rid: recs.get(rid))
    captured = {}
    def fake(*, system_blocks, user_text, schema, key, effort="high", client=None):
        captured["blocks"] = system_blocks
        return {"summary": "These verses address fasting.",
                "items": [{"record_id": "quran:2:183",
                           "framing": "Fasting is prescribed, as it was for those before."}]}
    monkeypatch.setattr(select.claude_client, "call_structured", fake)
    hits = [RetrievalHit("quran:2:183", 0.5, True, False)]
    out = select.select_and_frame(object(), "fasting?", hits, key="k")
    assert isinstance(out, Selection)
    assert out.items[0].record_id == "quran:2:183"
    # evidence block is a cached system block
    assert any(b.get("cache_control") for b in captured["blocks"])
    assert "quran:2:183" in captured["blocks"][-1]["text"]

def test_retry_feedback_reaches_the_prompt(monkeypatch):
    recs = {"quran:2:183": _Rec("quran:2:183", "Al-Baqarah 2:183", "x")}
    monkeypatch.setattr(select.db, "get_record", lambda c, rid: recs.get(rid))
    seen = {}
    def fake(*, system_blocks, user_text, schema, key, effort="high", client=None):
        seen["user"] = user_text
        return {"summary": "s", "items": []}
    monkeypatch.setattr(select.claude_client, "call_structured", fake)
    select.select_and_frame(object(), "q", [RetrievalHit("quran:2:183",0.1,True,False)],
                            key="k", feedback="Do not cite IDs outside the candidate set.")
    assert "candidate set" in seen["user"]
```

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement**

```python
# api/sanad/agents/select.py
from __future__ import annotations

from . import claude_client
from ..corpus import db
from ..pipeline.types import RetrievalHit, SelectedItem, Selection

SELECT_SYSTEM = (
    "You build an EVIDENCE BRIEF from a fixed candidate set of Qur'an verses "
    "and Sahih al-Bukhari hadith. Rules, all mandatory:\n"
    "1. You may ONLY cite record_ids that appear in the candidate set below.\n"
    "2. You write PROSE ONLY. Never output Arabic script — not a word, not a "
    "letter. The server renders the Arabic from the database by id.\n"
    "3. Choose only candidates genuinely relevant to the question. Omit the "
    "rest. Selecting nothing is a valid, honest outcome.\n"
    "4. For each chosen record write ONE framing line, at most 25 words, "
    "describing what the passage says. For a hadith this is your labelled "
    "explanation, NOT a translation.\n"
    "5. Write a neutral summary of at most 80 words of what the sources cover. "
    "Do not rule, do not grade authenticity, do not claim consensus.\n"
    "Return ONLY the structured object."
)

SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {"record_id": {"type": "string"},
                           "framing": {"type": "string"}},
            "required": ["record_id", "framing"],
            "additionalProperties": False,
        }},
    },
    "required": ["summary", "items"],
    "additionalProperties": False,
}


def build_evidence_block(corpus_conn, hits: list[RetrievalHit]) -> str:
    lines = ["CANDIDATE SET (cite only these record_ids):", ""]
    for h in hits:
        rec = db.get_record(corpus_conn, h.record_id)
        if rec is None:
            continue
        lines.append(f"[{rec.id}] {rec.reference_display}")
        lines.append(rec.text_ar)
        lines.append("")
    return "\n".join(lines)


def select_and_frame(corpus_conn, question: str, hits: list[RetrievalHit], *,
                     key: str, client=None, feedback: str | None = None) -> Selection:
    evidence = build_evidence_block(corpus_conn, hits)
    system_blocks = [
        {"type": "text", "text": SELECT_SYSTEM},
        {"type": "text", "text": evidence, "cache_control": {"type": "ephemeral"}},
    ]
    user = f"Question: {question}"
    if feedback:
        user += ("\n\nYour previous attempt was rejected. Fix exactly this and "
                 f"try again:\n{feedback}")
    data = claude_client.call_structured(
        system_blocks=system_blocks, user_text=user, schema=SELECT_SCHEMA,
        key=key, client=client)
    return Selection(
        summary=data["summary"],
        items=[SelectedItem(record_id=i["record_id"], framing=i["framing"])
               for i in data["items"]])
```

- [ ] **Step 4: Run, confirm pass.**

- [ ] **Step 5: Commit**

```bash
git add api/sanad/agents/select.py tests/agents/test_select.py
git commit -m "feat(agents): stage 3 select-and-frame with cached evidence prefix"
```

---

## Task 8: Stage 4 — the guards (safety-critical, its own task)

**Files:**
- Create: `api/sanad/pipeline/guards.py`
- Test: `tests/pipeline/test_guards.py`

**Interfaces:**
- Consumes: `pipeline.types.{Selection,GuardResult}`.
- Produces:
  - `check(selection, candidate_ids: set[str]) -> list[GuardResult]` — every guard, in the spec §5 strength order. `all(g.passed for g in ...)` is the block decision.
  - `GRADING_TERMS`, `COLLECTION_TITLES`, `NAME_PARTICLES` — the one named constant with its reasoning beside it.
  - `contains_arabic(s: str) -> bool`, `word_count(s: str) -> int`.

**This is the safety-critical task; the guards are the structural guarantee.** From spec §5, ordered by how well they actually work:

1. **Cited ID in candidate set** — airtight. Every item's `record_id` must be in `candidate_ids`.
2. **No Arabic in generated prose** — airtight. Any Arabic codepoint (`؀-ۿ`, `ݐ-ݿ`, `ﭐ-﷿`, `ﹰ-﻿`) in any `framing` or the `summary` blocks. This is what makes fabrication structurally impossible.
3. **Length bounds** — airtight. `summary` ≤ 80 words, each `framing` ≤ 25 words.
4. **No unanimity claim** — good. Narrow vocabulary: ijmāʿ, "all scholars agree", "unanimously", "there is no disagreement".
5. **No grading vocabulary** — partial, deliberately. **Not a bare wordlist** — `sahih` is half the collection's title, `hasan` is a narrator's name. Block a grading term only where it is NOT part of a known collection title AND NOT immediately adjacent to a name particle (`ibn`/`bin`/`al-`/`abu`). Terms: صحيح/`sahih`/`saheeh`/`ṣaḥīḥ`, ضعيف/`daif`/`da'if`/`daeef`/`ḍaʿīf`, موضوع/`mawdu`/`mawdoo`/`mawḍūʿ`, `matruk`. `hasan`/`munkar` are excluded from the hard block (too collision-prone) and left to stage 5.

**Write the Arabic ranges as explicit `\uXXXX` escapes and print the compiled pattern once** (`sanad-character-transit-defect`): eyeballing cannot catch a wrong combining-mark range.

- [ ] **Step 1: Write the failing test** — one case per attack, plus the collisions that MUST pass

```python
# tests/pipeline/test_guards.py
from sanad.pipeline.guards import check
from sanad.pipeline.types import Selection, SelectedItem

CANDS = {"quran:2:183", "hadith:bukhari:2866"}

def _sel(summary="Sources on the topic.", items=None):
    return Selection(summary=summary,
                     items=items or [SelectedItem("quran:2:183", "A framing.")])

def _blocked(sel, name):
    results = check(sel, CANDS)
    g = next(r for r in results if r.name == name)
    return not g.passed

def test_all_pass_on_a_clean_brief():
    assert all(r.passed for r in check(_sel(), CANDS))

def test_blocks_id_outside_candidate_set():
    sel = _sel(items=[SelectedItem("quran:9:9999", "Fabricated.")])
    assert _blocked(sel, "cited_id_in_candidates")

def test_blocks_arabic_in_framing():
    sel = _sel(items=[SelectedItem("quran:2:183", "It reads كتب عليكم.")])
    assert _blocked(sel, "no_arabic_in_prose")

def test_blocks_arabic_in_summary():
    assert _blocked(_sel(summary="The verse الصيام is relevant."), "no_arabic_in_prose")

def test_blocks_overlong_summary():
    assert _blocked(_sel(summary=" ".join(["word"] * 81)), "length_bounds")

def test_blocks_overlong_framing():
    sel = _sel(items=[SelectedItem("quran:2:183", " ".join(["w"] * 26))])
    assert _blocked(sel, "length_bounds")

def test_blocks_unanimity_claim():
    assert _blocked(_sel(summary="All scholars agree this is obligatory."),
                    "no_unanimity")

def test_blocks_grading_claim():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866", "This hadith is sahih.")])
    assert _blocked(sel, "no_grading")

# --- collisions that MUST PASS (a guard that suppresses correct output fails) ---
def test_citation_of_sahih_al_bukhari_passes():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "Reported in Sahih al-Bukhari 2866 on striving.")])
    assert all(r.passed for r in check(sel, CANDS))

def test_naming_al_hasan_al_basri_passes():
    sel = _sel(items=[SelectedItem("hadith:bukhari:2866",
                                   "Narrated via al-Hasan al-Basri about patience.")])
    assert all(r.passed for r in check(sel, CANDS))
```

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement**

```python
# api/sanad/pipeline/guards.py
from __future__ import annotations

import re

from .types import GuardResult, Selection

# Arabic blocks, written as explicit escapes and compiled once. PRINT the
# compiled pattern during review (see sanad-character-transit-defect): a wrong
# combining-mark range is invisible on screen.
#   ؀-ۿ Arabic, ݐ-ݿ Supplement,
#   ﭐ-﷿ Arabic Presentation Forms-A, ﹰ-﻿ Forms-B
_ARABIC = re.compile("[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")

SUMMARY_MAX_WORDS = 80
FRAMING_MAX_WORDS = 25

_UNANIMITY = re.compile(
    r"\b(ijma'?|unanimous(ly)?|all scholars agree|there is no disagreement|"
    r"scholarly consensus|consensus of the scholars)\b", re.IGNORECASE)

# The grading guard is PARTIAL by design (spec §5). Block a grading term only
# where it is not part of a collection title and not adjacent to a name
# particle. 'hasan'/'munkar' are deliberately NOT here.
GRADING_TERMS = ("sahih", "saheeh", "صحيح",  # صحيح
                 "daif", "da'if", "daeef", "ضعيف",  # ضعيف
                 "mawdu", "mawdoo", "موضوع",  # موضوع
                 "matruk")
COLLECTION_TITLES = ("sahih al-bukhari", "sahih muslim", "sahih al bukhari")
NAME_PARTICLES = ("ibn", "bin", "al-", "abu")


def contains_arabic(s: str) -> bool:
    return _ARABIC.search(s) is not None


def word_count(s: str) -> int:
    return len(s.split())


def _grading_offends(text: str) -> bool:
    low = text.lower()
    stripped = low
    for title in COLLECTION_TITLES:              # remove legitimate titles first
        stripped = stripped.replace(title, " ")
    for m in re.finditer(r"[\w'\-؀-ۿ]+", stripped):
        tok = m.group(0)
        if tok not in GRADING_TERMS:
            continue
        before = stripped[:m.start()].rstrip().split()
        prev = before[-1] if before else ""
        if any(prev.startswith(p) or prev == p.rstrip("-") for p in NAME_PARTICLES):
            continue                              # e.g. "al-hasan" style adjacency
        return True
    return False


def check(selection: Selection, candidate_ids: set[str]) -> list[GuardResult]:
    prose = [selection.summary] + [i.framing for i in selection.items]
    joined = " ".join(prose)

    stray = [i.record_id for i in selection.items if i.record_id not in candidate_ids]
    len_ok = (word_count(selection.summary) <= SUMMARY_MAX_WORDS
              and all(word_count(i.framing) <= FRAMING_MAX_WORDS
                      for i in selection.items))

    return [
        GuardResult("cited_id_in_candidates", not stray,
                    "" if not stray else f"ids outside candidate set: {stray}"),
        GuardResult("no_arabic_in_prose", not any(contains_arabic(p) for p in prose),
                    "" if not any(contains_arabic(p) for p in prose)
                    else "Arabic script in generated prose"),
        GuardResult("length_bounds", len_ok,
                    "" if len_ok else "summary >80 or a framing >25 words"),
        GuardResult("no_unanimity", _UNANIMITY.search(joined) is None,
                    "" if _UNANIMITY.search(joined) is None else "unanimity claimed"),
        GuardResult("no_grading", not _grading_offends(joined),
                    "" if not _grading_offends(joined) else "grading vocabulary used"),
    ]
```

- [ ] **Step 4: Run, confirm pass** — `pytest tests/pipeline/test_guards.py -v` (10 tests).

- [ ] **Step 5: Print the compiled Arabic pattern once and confirm the range**

Run: `python -c "from sanad.pipeline.guards import _ARABIC; print(_ARABIC.pattern); print(_ARABIC.search('sahih'), _ARABIC.search('كتب'))"`
Expected: `None` for `sahih`, a match object for `كتب`. Confirms the class matches Arabic and not Latin.

- [ ] **Step 6: Commit**

```bash
git add api/sanad/pipeline/guards.py tests/pipeline/test_guards.py
git commit -m "feat(pipeline): stage 4 guards — structural fabrication and grading blocks"
```

---

## Task 9: Stage 5 audit + Stage 6 adjudicate

**Files:**
- Create: `api/sanad/agents/audit.py`, `api/sanad/pipeline/adjudicate.py`
- Test: `tests/agents/test_audit.py`, `tests/pipeline/test_adjudicate.py`

**Interfaces:**
- Consumes: `agents.claude_client` (module-qualified); `corpus.db.get_record`; `pipeline.types.{Selection,AuditVerdict,GuardResult}`.
- Produces:
  - `audit_brief(corpus_conn, selection, *, key, client=None) -> AuditVerdict` — a fresh Claude call judging whether each framing is supported by the record it sits under; flags overreach, unanimity, flattened madhhab disagreement, implied grading. Context-isolated: receives only the brief and the evidence, never stage 3's prompt/reasoning.
  - `AUDIT_SYSTEM`, `AUDIT_SCHEMA`.
  - `Decision` enum: `PUBLISH`, `RELABEL_INTERPRETATION`, `RETRY`, `ABSTAIN`.
  - `adjudicate(*, guard_results, audit, risk_label, attempt) -> Decision` — the deterministic stage 6 rule.

**Adjudication rule (spec §2, §6):**
- guards blocked → `RETRY` on attempt 0, `ABSTAIN` on attempt 1.
- guards pass, audit overreach → `RETRY` on attempt 0, `ABSTAIN` on attempt 1.
- guards pass, audit clean, `risk_label == DISPUTED` → `RELABEL_INTERPRETATION` (published, labelled).
- guards pass, audit clean, otherwise → `PUBLISH`.

- [ ] **Step 1: Write the failing test for audit**

```python
# tests/agents/test_audit.py
from sanad.agents import audit
from sanad.pipeline.types import Selection, SelectedItem, AuditVerdict

class _Rec:
    def __init__(self, rid, text): self.id, self.reference_display, self.text_ar = rid, rid, text

def test_audit_parses_verdict(monkeypatch):
    monkeypatch.setattr(audit.db, "get_record",
                        lambda c, rid: _Rec(rid, "arabic"))
    def fake(*, system_blocks, user_text, schema, key, effort="high", client=None):
        # auditor must NOT receive stage-3 reasoning; only brief + evidence
        return {"overreach": False, "flags": []}
    monkeypatch.setattr(audit.claude_client, "call_structured", fake)
    sel = Selection("summary", [SelectedItem("quran:2:183", "framing")])
    v = audit.audit_brief(object(), sel, key="k")
    assert isinstance(v, AuditVerdict) and v.overreach is False

def test_audit_reports_overreach(monkeypatch):
    monkeypatch.setattr(audit.db, "get_record", lambda c, rid: _Rec(rid, "x"))
    monkeypatch.setattr(audit.claude_client, "call_structured",
        lambda **kw: {"overreach": True, "flags": ["framing misrepresents ayah"]})
    v = audit.audit_brief(object(), Selection("s", [SelectedItem("quran:2:183","f")]), key="k")
    assert v.overreach is True and v.flags
```

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement audit**

```python
# api/sanad/agents/audit.py
from __future__ import annotations

from . import claude_client
from ..corpus import db
from ..pipeline.types import AuditVerdict, Selection

AUDIT_SYSTEM = (
    "You are an independent reviewer. You are shown an evidence brief (a summary "
    "and framing lines, each under a record) and the Arabic source records. You "
    "did NOT write the brief and must not assume its framings are correct. For "
    "each framing, judge ONLY whether it is fairly supported by the record it "
    "sits under. Flag: overreach (a framing claiming more than the passage "
    "says), any claim of unanimity/consensus, any flattening of madhhab "
    "disagreement into one position, and any implied authenticity grading. "
    "Set overreach true if ANY framing or the summary overreaches. Return ONLY "
    "the structured object."
)

AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "overreach": {"type": "boolean"},
        "flags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["overreach", "flags"],
    "additionalProperties": False,
}


def audit_brief(corpus_conn, selection: Selection, *, key: str,
                client=None) -> AuditVerdict:
    lines = [f"SUMMARY: {selection.summary}", "", "BRIEF ITEMS AND SOURCES:"]
    for item in selection.items:
        rec = db.get_record(corpus_conn, item.record_id)
        lines.append(f"- framing: {item.framing}")
        lines.append(f"  record [{item.record_id}]: {rec.text_ar if rec else '(missing)'}")
    data = claude_client.call_structured(
        system_blocks=[{"type": "text", "text": AUDIT_SYSTEM}],
        user_text="\n".join(lines), schema=AUDIT_SCHEMA, key=key, client=client)
    return AuditVerdict(overreach=bool(data["overreach"]),
                        flags=list(data["flags"]))
```

- [ ] **Step 4: Write the failing test for adjudicate**

```python
# tests/pipeline/test_adjudicate.py
from sanad.pipeline.adjudicate import adjudicate, Decision
from sanad.pipeline.types import GuardResult, AuditVerdict

def _guards(passed): return [GuardResult("g", passed, "")]

def test_guard_block_retries_then_abstains():
    assert adjudicate(guard_results=_guards(False), audit=None,
                      risk_label="GENERAL", attempt=0) is Decision.RETRY
    assert adjudicate(guard_results=_guards(False), audit=None,
                      risk_label="GENERAL", attempt=1) is Decision.ABSTAIN

def test_audit_overreach_retries_then_abstains():
    ov = AuditVerdict(overreach=True, flags=["x"])
    assert adjudicate(guard_results=_guards(True), audit=ov,
                      risk_label="GENERAL", attempt=0) is Decision.RETRY
    assert adjudicate(guard_results=_guards(True), audit=ov,
                      risk_label="GENERAL", attempt=1) is Decision.ABSTAIN

def test_clean_general_publishes():
    clean = AuditVerdict(overreach=False, flags=[])
    assert adjudicate(guard_results=_guards(True), audit=clean,
                      risk_label="GENERAL", attempt=0) is Decision.PUBLISH

def test_clean_disputed_relabels():
    clean = AuditVerdict(overreach=False, flags=[])
    assert adjudicate(guard_results=_guards(True), audit=clean,
                      risk_label="DISPUTED", attempt=0) is Decision.RELABEL_INTERPRETATION
```

- [ ] **Step 5: Run both audit + adjudicate tests, confirm fail.**

- [ ] **Step 6: Implement adjudicate**

```python
# api/sanad/pipeline/adjudicate.py
from __future__ import annotations

from enum import Enum

from .types import AuditVerdict, GuardResult


class Decision(str, Enum):
    PUBLISH = "PUBLISH"
    RELABEL_INTERPRETATION = "RELABEL_INTERPRETATION"
    RETRY = "RETRY"
    ABSTAIN = "ABSTAIN"


def adjudicate(*, guard_results: list[GuardResult], audit: AuditVerdict | None,
               risk_label: str, attempt: int) -> Decision:
    guards_blocked = not all(g.passed for g in guard_results)
    overreached = audit is not None and audit.overreach
    if guards_blocked or overreached:
        return Decision.RETRY if attempt == 0 else Decision.ABSTAIN
    if risk_label == "DISPUTED":
        return Decision.RELABEL_INTERPRETATION
    return Decision.PUBLISH
```

- [ ] **Step 7: Run both test files, confirm pass.**

- [ ] **Step 8: Commit**

```bash
git add api/sanad/agents/audit.py api/sanad/pipeline/adjudicate.py \
        tests/agents/test_audit.py tests/pipeline/test_adjudicate.py
git commit -m "feat(pipeline): stage 5 context-isolated audit and stage 6 adjudication"
```

---
## Task 10: Pipeline orchestration (stage 0 router + the seven-stage loop)

**Files:**
- Create: `api/sanad/pipeline/orchestrate.py`
- Test: `tests/pipeline/test_orchestrate.py`

**Interfaces:**
- Consumes: `verify.claims.{route_risk,requires_handoff,RiskCode}`; `retrieve.retrieve.retrieve`; `agents.{expand,select,audit}`; `pipeline.{guards,adjudicate}`; `pipeline.types.StageEvent`; `corpus.scope.CORPUS_SCOPE`; `agents.claude_client.ClaudeError`; `retrieve.voyage.resolve_voyage_key`, `agents.claude_client.resolve_anthropic_key`.
- Produces:
  - `run_ask(corpus_conn, vectors_conn, question, *, anthropic_key, voyage_key, deps=DEFAULT_DEPS) -> Iterator[StageEvent]` — a generator yielding one `StageEvent` per stage and a terminal `final`/`error` event. `deps` is a small struct of the stage callables so tests inject fakes.
  - `DEFAULT_DEPS` binding the real stage functions.
  - `AskOutcome` assembled into the `final` event payload (see Task 11 schema).

**This is where the whole spec §2 flow lives.** Order and rules:
1. `router`: `route_risk(question)`. If `requires_handoff` → emit `router` with the handoff packet and STOP (no later stage). Else emit `router` with `risk`, `requires_handoff=False`, and carry the `DISPUTED`/`GENERAL` label.
2. `expand`: `expand_query`. On `ClaudeError` → emit `error` and abstain (Ask needs the terms). Emit `expand` with language + terms.
3. `retrieve`: `retrieve(...)`. Emit `retrieve` with `candidate_count`, `reached`, `unreached_reason`. If no hits → abstain with the scope wording (spec §6), still a success `final` with `status="abstained"`.
4. `select` → `check` → `audit` → `adjudicate`, with **exactly one retry**: on `RETRY`, re-run `select_and_frame` with feedback built from the failed guards / audit flags, then `check`/`audit`/`adjudicate` again (attempt=1). On the second failure `adjudicate` returns `ABSTAIN`.
5. Emit `select`, `check`, `audit` events each attempt; then `final`.
- Any `ClaudeError` in select/audit → emit `error`, abstain. **A model failure is never a 500** (Review Focus).
- The `final` payload carries `question_language`, `summary`/`items` (with server-rendered records via `db.get_record` — Task 11 does the rendering in the route; orchestrate passes record_ids + framings), `reached`, `unreached_reason`, `risk`, `requires_handoff`, `abstain_reason`, and `status`.

- [ ] **Step 1: Write the failing test** (inject fake deps; no network, no real Claude)

```python
# tests/pipeline/test_orchestrate.py
from types import SimpleNamespace

from sanad.pipeline import orchestrate
from sanad.pipeline.types import (Expansion, RetrievalResult, RetrievalHit,
                                   Selection, SelectedItem, AuditVerdict, GuardResult)


def _deps(**over):
    base = dict(
        expand=lambda q, *, key, client=None: Expansion("en", ["صبر"]),
        retrieve=lambda cc, vc, *, arabic_terms, question, voyage_key, embed_fn=None:
            RetrievalResult([RetrievalHit("quran:2:183", 0.5, True, False)],
                            {"quran": True, "hadith": False}, None, 1),
        select=lambda cc, q, hits, *, key, client=None, feedback=None:
            Selection("Summary.", [SelectedItem("quran:2:183", "Framing.")]),
        guards=lambda sel, cands: [GuardResult("g", True, "")],
        audit=lambda cc, sel, *, key, client=None: AuditVerdict(False, []),
    )
    base.update(over)
    return SimpleNamespace(**base)


def _run(question, deps, risk="GENERAL"):
    import sanad.pipeline.orchestrate as o
    o.route_risk = lambda t: __import__("sanad.verify.claims", fromlist=["RiskCode"]).RiskCode(risk)
    return list(orchestrate.run_ask(object(), object(), question,
                                    anthropic_key="a", voyage_key=None, deps=deps))


def test_happy_path_publishes():
    events = _run("How to be patient?", _deps())
    stages = [e.stage for e in events]
    assert stages[0] == "router" and stages[-1] == "final"
    final = events[-1].payload
    assert final["status"] == "published"
    assert final["items"][0]["record_id"] == "quran:2:183"


def test_personal_ruling_stops_after_router():
    events = _run("Can I divorce my wife?", _deps(), risk="PERSONAL_RULING")
    assert [e.stage for e in events] == ["router"]
    assert events[0].payload["requires_handoff"] is True


def test_guard_block_then_clean_retry_publishes():
    calls = {"n": 0}
    def flaky_guards(sel, cands):
        calls["n"] += 1
        return [GuardResult("g", calls["n"] > 1, "bad" if calls["n"] == 1 else "")]
    events = _run("q", _deps(guards=flaky_guards))
    assert events[-1].payload["status"] == "published"
    assert calls["n"] == 2  # retried once

def test_second_failure_abstains():
    events = _run("q", _deps(guards=lambda s, c: [GuardResult("g", False, "bad")]))
    assert events[-1].payload["status"] == "abstained"
    assert events[-1].payload["abstain_reason"]

def test_no_candidates_abstains_with_scope():
    from sanad.corpus.scope import CORPUS_SCOPE
    empty = lambda cc, vc, *, arabic_terms, question, voyage_key, embed_fn=None: \
        RetrievalResult([], {"quran": False, "hadith": False}, "nada", 0)
    events = _run("q", _deps(retrieve=empty))
    p = events[-1].payload
    assert p["status"] == "abstained" and "Sahih al-Bukhari" in p["abstain_reason"]

def test_claude_error_in_expand_abstains_not_raises():
    from sanad.agents.claude_client import ClaudeError
    def boom(q, *, key, client=None): raise ClaudeError("refused")
    events = _run("q", _deps(expand=boom))
    assert events[-1].stage in ("error", "final")
    assert events[-1].payload.get("status") == "abstained" or events[-1].stage == "error"
```

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement**

```python
# api/sanad/pipeline/orchestrate.py
from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

from ..agents import audit as _audit
from ..agents import expand as _expand
from ..agents import select as _select
from ..agents.claude_client import ClaudeError
from ..corpus.scope import CORPUS_SCOPE
from ..verify.claims import RiskCode, requires_handoff, route_risk
from . import guards as _guards
from .adjudicate import Decision, adjudicate
from .types import StageEvent

DEFAULT_DEPS = SimpleNamespace(
    expand=_expand.expand_query,
    retrieve=None,   # bound below to avoid an import cycle at module import
    select=_select.select_and_frame,
    guards=_guards.check,
    audit=_audit.audit_brief,
)


def _bind_retrieve():
    from ..retrieve.retrieve import retrieve
    DEFAULT_DEPS.retrieve = retrieve
    return DEFAULT_DEPS


def _feedback(guard_results, audit) -> str:
    parts = [g.detail for g in guard_results if not g.passed and g.detail]
    if audit is not None and audit.overreach:
        parts.extend(audit.flags)
    return "; ".join(parts) or "The brief was rejected; be more conservative."


def _final(*, status, question_language, summary, items, reached,
           unreached_reason, risk, abstain_reason=None):
    return StageEvent("final", {
        "status": status,
        "question_language": question_language,
        "summary": summary,
        "items": items,                 # [{record_id, framing}] — route renders records
        "reached": reached,
        "unreached_reason": unreached_reason,
        "risk": risk,
        "requires_handoff": False,
        "abstain_reason": abstain_reason,
    })


def run_ask(corpus_conn, vectors_conn, question, *, anthropic_key,
            voyage_key, deps=None) -> Iterator[StageEvent]:
    deps = deps or (DEFAULT_DEPS if DEFAULT_DEPS.retrieve else _bind_retrieve())

    risk = route_risk(question)
    if requires_handoff(risk):
        yield StageEvent("router", {"risk": risk.value, "requires_handoff": True,
                                    "corpus_scope": CORPUS_SCOPE})
        return
    yield StageEvent("router", {"risk": risk.value, "requires_handoff": False})

    try:
        expansion = deps.expand(question, key=anthropic_key)
    except ClaudeError as exc:
        yield StageEvent("error", {"code": "expand_failed", "message": str(exc)})
        yield _final(status="abstained", question_language=None, summary=None,
                     items=[], reached={"quran": False, "hadith": False},
                     unreached_reason=None, risk=risk.value,
                     abstain_reason="Query expansion was unavailable.")
        return
    yield StageEvent("expand", {"question_language": expansion.question_language,
                                "search_terms": expansion.search_terms})

    result = deps.retrieve(corpus_conn, vectors_conn,
                           arabic_terms=expansion.search_terms, question=question,
                           voyage_key=voyage_key)
    yield StageEvent("retrieve", {"candidate_count": result.candidate_count,
                                  "reached": result.reached,
                                  "unreached_reason": result.unreached_reason})
    if not result.hits:
        yield _final(status="abstained",
                     question_language=expansion.question_language, summary=None,
                     items=[], reached=result.reached,
                     unreached_reason=result.unreached_reason, risk=risk.value,
                     abstain_reason=CORPUS_SCOPE)
        return

    candidate_ids = {h.record_id for h in result.hits}
    feedback = None
    for attempt in (0, 1):
        try:
            selection = deps.select(corpus_conn, question, result.hits,
                                    key=anthropic_key, feedback=feedback)
        except ClaudeError as exc:
            yield StageEvent("error", {"code": "select_failed", "message": str(exc)})
            yield _final(status="abstained",
                         question_language=expansion.question_language, summary=None,
                         items=[], reached=result.reached,
                         unreached_reason=result.unreached_reason, risk=risk.value,
                         abstain_reason="The brief could not be generated.")
            return
        yield StageEvent("select", {
            "summary": selection.summary,
            "items": [{"record_id": i.record_id, "framing": i.framing}
                      for i in selection.items]})

        guard_results = deps.guards(selection, candidate_ids)
        yield StageEvent("check", {"guards": [
            {"name": g.name, "pass": g.passed, "detail": g.detail}
            for g in guard_results]})

        audit = None
        if all(g.passed for g in guard_results):
            try:
                audit = deps.audit(corpus_conn, selection, key=anthropic_key)
            except ClaudeError as exc:
                yield StageEvent("error", {"code": "audit_failed", "message": str(exc)})
                yield _final(status="abstained",
                             question_language=expansion.question_language,
                             summary=None, items=[], reached=result.reached,
                             unreached_reason=result.unreached_reason,
                             risk=risk.value,
                             abstain_reason="The brief could not be reviewed.")
                return
            yield StageEvent("audit", {"overreach": audit.overreach,
                                       "flags": audit.flags})

        decision = adjudicate(guard_results=guard_results, audit=audit,
                              risk_label=risk.value, attempt=attempt)
        if decision in (Decision.PUBLISH, Decision.RELABEL_INTERPRETATION):
            status = ("published" if decision is Decision.PUBLISH
                      else "published")  # relabel is still published, with DISPUTED risk
            yield _final(status=status,
                         question_language=expansion.question_language,
                         summary=selection.summary,
                         items=[{"record_id": i.record_id, "framing": i.framing}
                                for i in selection.items],
                         reached=result.reached,
                         unreached_reason=result.unreached_reason, risk=risk.value)
            return
        if decision is Decision.ABSTAIN:
            break
        feedback = _feedback(guard_results, audit)  # RETRY

    yield _final(status="abstained", question_language=expansion.question_language,
                 summary=None, items=[], reached=result.reached,
                 unreached_reason=result.unreached_reason, risk=risk.value,
                 abstain_reason="The brief did not pass review after one retry.")
```

> **Note on `DISPUTED` relabel:** the `final` event's `risk` already carries `DISPUTED`, so the frontend renders the interpretation label off `risk`; there is no separate status string, keeping the `status` field to the two values the spec's payload names (`published`/`abstained`).

- [ ] **Step 4: Run, confirm pass** — `pytest tests/pipeline/test_orchestrate.py -v`.

- [ ] **Step 5: Commit**

```bash
git add api/sanad/pipeline/orchestrate.py tests/pipeline/test_orchestrate.py
git commit -m "feat(pipeline): seven-stage orchestration with one-retry loop"
```

---

## Task 11: `POST /api/ask` — SSE route + schemas + R46 wiring

**Files:**
- Modify: `api/sanad/api/schemas.py` (add `AskRequest`, `AskItemOut`, `ReachedOut`, `AskFinalOut`)
- Modify: `api/sanad/api/routes.py` (add the SSE route; render records by ID; audit-log rows)
- Modify: `api/sanad/api/app.py` (open the vectors sidecar connection on startup, if present)
- Test: `tests/api/test_ask_route.py`

**Interfaces:**
- Consumes: `pipeline.orchestrate.run_ask`; `pipeline.types.StageEvent`; `agents.claude_client.resolve_anthropic_key`; `retrieve.voyage.resolve_voyage_key`; `retrieve.vector_store.connect_vectors`; `corpus.db.get_record`; `api._record_out`.
- Produces: `POST /api/ask` streaming `text/event-stream`, one SSE `data:` line per `StageEvent`. On the `final` event, each item is enriched with its rendered `record` (server-read from the DB by ID — spec §7). The five existing endpoints are untouched.

**Server renders records — never echoes model output** (spec §1, §7). The `final` event's `items` carry `record_id` + `framing` from orchestrate; the route inlines `record = _record_out(conn, db.get_record(conn, record_id))`.

**Availability:** if `resolve_anthropic_key()` is None, `/api/ask` returns a `final` abstain event stating Ask needs an Anthropic key, with `reached` both false — Verify stays fully functional (spec §3.5). The vectors sidecar connection is optional: absent → `voyage_key=None` path, lexical-only.

**App startup:** open a read-only `connect_vectors` on `resolve_vectors_db_path()` (new in `settings.py`, env `SANAD_VECTORS_DB` else `data/sanad-vectors.db`, returns None if absent) into `app.state.vectors_conn`.

**Audit log (spec §9):** on the `final` event write ONE `audit_log` row: `stage="ask"`, `verdict=status`, `detail_json={risk, record_ids, abstained: bool, reached}`. **Never the question or the search terms.** Reuse `app.state.audit_lock` exactly as `verify()` does.

- [ ] **Step 1: Write the failing test** (fake `run_ask` via monkeypatch; use FastAPI TestClient)

```python
# tests/api/test_ask_route.py
import json
from fastapi.testclient import TestClient

def _events_from(resp_text):
    return [json.loads(line[len("data: "):])
            for line in resp_text.splitlines() if line.startswith("data: ")]

def test_ask_streams_events_and_renders_records(monkeypatch, tmp_path):
    import sanad.api.routes as routes
    from sanad.pipeline.types import StageEvent
    def fake_run(cc, vc, q, *, anthropic_key, voyage_key, deps=None):
        yield StageEvent("router", {"risk": "GENERAL", "requires_handoff": False})
        yield StageEvent("final", {
            "status": "published", "question_language": "en",
            "summary": "Sources on patience.",
            "items": [{"record_id": "quran:2:153", "framing": "Seek help in patience."}],
            "reached": {"quran": True, "hadith": False}, "unreached_reason": None,
            "risk": "GENERAL", "requires_handoff": False, "abstain_reason": None})
    monkeypatch.setattr(routes, "run_ask", fake_run)
    monkeypatch.setattr(routes, "resolve_anthropic_key", lambda: "a")
    client = _make_client(tmp_path)  # helper builds app over the shipped test corpus
    r = client.post("/api/ask", json={"question": "patience?"})
    assert r.status_code == 200
    events = _events_from(r.text)
    assert events[0]["stage"] == "router"
    final = events[-1]["payload"]
    assert final["items"][0]["record"]["id"] == "quran:2:153"   # server-rendered
    assert "text_ar" in final["items"][0]["record"]

def test_ask_without_key_abstains(monkeypatch, tmp_path):
    import sanad.api.routes as routes
    monkeypatch.setattr(routes, "resolve_anthropic_key", lambda: None)
    client = _make_client(tmp_path)
    r = client.post("/api/ask", json={"question": "x"})
    events = _events_from(r.text)
    assert events[-1]["payload"]["status"] == "abstained"
    assert events[-1]["payload"]["reached"] == {"quran": False, "hadith": False}

def test_ask_rejects_blank_question(tmp_path):
    client = _make_client(tmp_path)
    assert client.post("/api/ask", json={"question": "  "}).status_code == 422
```

(`_make_client` mirrors the existing route tests' fixture: `create_app()` with `SANAD_DB` pointed at the committed corpus and `SANAD_AUDIT_DB` at a tmp file. Reuse the helper from `tests/api/test_routes.py`.)

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Add the schemas**

```python
# api/sanad/api/schemas.py — append
class AskRequest(BaseModel):
    question: str = Field(..., max_length=2000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v


class ReachedOut(BaseModel):
    quran: bool
    hadith: bool


class AskItemOut(BaseModel):
    record_id: str
    framing: str
    record: RecordOut | None = None


class AskFinalOut(BaseModel):
    status: str                       # "published" | "abstained"
    question_language: str | None = None
    summary: str | None = None
    items: list[AskItemOut] = Field(default_factory=list)
    reached: ReachedOut
    unreached_reason: str | None = None
    risk: str
    requires_handoff: bool = False
    abstain_reason: str | None = None
    corpus_scope: str
```

- [ ] **Step 4: Add the route** (`api/sanad/api/routes.py`)

```python
# imports
import asyncio
from fastapi.responses import StreamingResponse
from ..agents.claude_client import resolve_anthropic_key
from ..retrieve.voyage import resolve_voyage_key
from ..pipeline.orchestrate import run_ask
from .schemas import AskRequest  # (AskFinalOut used for documentation/shape)

@router.post("/ask")
def ask(payload: AskRequest, request: Request) -> StreamingResponse:
    conn = _conn(request)
    vectors_conn = getattr(request.app.state, "vectors_conn", None)
    anthropic_key = resolve_anthropic_key()
    voyage_key = resolve_voyage_key()

    def _sse() -> "Iterator[str]":
        record_ids: list[str] = []
        status = "abstained"
        risk = "GENERAL"
        reached = {"quran": False, "hadith": False}

        if anthropic_key is None:
            final = {
                "stage": "final",
                "payload": {
                    "status": "abstained", "question_language": None,
                    "summary": None, "items": [],
                    "reached": {"quran": False, "hadith": False},
                    "unreached_reason": None, "risk": "GENERAL",
                    "requires_handoff": False,
                    "abstain_reason": ("Ask needs an Anthropic API key, which is "
                                       "not configured. Verification is unaffected."),
                    "corpus_scope": CORPUS_SCOPE}}
            yield f"data: {json.dumps(final)}\n\n"
            _write_ask_audit(request, "abstained", "GENERAL", [], reached)
            return

        for event in run_ask(conn, vectors_conn, payload.question,
                             anthropic_key=anthropic_key, voyage_key=voyage_key):
            payload_out = dict(event.payload)
            if event.stage == "final":
                items = []
                for it in payload_out.get("items", []):
                    rec = db.get_record(conn, it["record_id"])
                    items.append({
                        "record_id": it["record_id"], "framing": it["framing"],
                        "record": _record_out(conn, rec).model_dump() if rec else None})
                payload_out["items"] = items
                payload_out["corpus_scope"] = CORPUS_SCOPE
                record_ids = [it["record_id"] for it in items]
                status = payload_out.get("status", "abstained")
                risk = payload_out.get("risk", "GENERAL")
                reached = payload_out.get("reached", reached)
            yield f"data: {json.dumps({'stage': event.stage, 'payload': payload_out})}\n\n"

        _write_ask_audit(request, status, risk, record_ids, reached)

    return StreamingResponse(_sse(), media_type="text/event-stream")


def _write_ask_audit(request, status, risk, record_ids, reached) -> None:
    audit_conn = _audit_conn(request)
    with request.app.state.audit_lock:
        audit_conn.execute(
            "INSERT INTO audit_log (ts, request_id, stage, verdict, detail_json) "
            "VALUES (?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), str(uuid.uuid4()), "ask",
             status,
             json.dumps({"risk": risk, "record_ids": record_ids,
                         "abstained": status == "abstained", "reached": reached})))
        audit_conn.commit()
```

> The question text and search terms are never in `detail_json` — same rule as `verify()`. Records are rendered by the server via `db.get_record` + `_record_out`, never echoed from the model.

- [ ] **Step 5: Wire the vectors connection in `app.py` and `settings.py`**

```python
# api/sanad/settings.py — append
def resolve_vectors_db_path() -> Path | None:
    override = os.environ.get("SANAD_VECTORS_DB")
    if override:
        p = Path(override)
        return p if p.is_file() else None
    p = Path("data/sanad-vectors.db")
    return p if p.is_file() else None
```

```python
# api/sanad/api/app.py — in create_app(), after audit_conn is set
    from ..settings import resolve_vectors_db_path
    from ..retrieve.vector_store import connect_vectors
    vectors_path = resolve_vectors_db_path()
    app.state.vectors_conn = (
        connect_vectors(vectors_path, read_only=True) if vectors_path else None)
    log.info("vectors %s", vectors_path or "(absent — Ask runs lexical-only)")
```

- [ ] **Step 6: Run the route tests, confirm pass** — `pytest tests/api/test_ask_route.py -v`.

- [ ] **Step 7: Regenerate the API client (drift gate)**

Run: `cd web && npm run generate:client && git diff src/api/types.ts`
Expected: `types.ts` gains the Ask models. Commit the regenerated file — CI's web job fails on drift.

- [ ] **Step 8: Commit**

```bash
git add api/sanad/api/schemas.py api/sanad/api/routes.py api/sanad/api/app.py \
        api/sanad/settings.py tests/api/test_ask_route.py web/src/api/types.ts
git commit -m "feat(api): POST /api/ask SSE route rendering records server-side"
```

---

## Task 12: The Ask eval gate (adversarial stage-3 fixtures)

**Files:**
- Create: `eval/cases/ask/adversarial.json`, `eval/cases/ask/must_pass.json`
- Create: `eval/ask_runner.py`
- Modify: `.github/workflows/ci.yml` (add the gate step)
- Test: `tests/eval/test_ask_runner.py`

**Interfaces:**
- Consumes: `pipeline.guards.check`; `pipeline.types.{Selection,SelectedItem}`.
- Produces: `load_ask_cases(dir) -> list[AskCase]`; `run_ask_gate(cases) -> AskMetrics`; a `main()` returning nonzero on any breach. `AskCase` fields: `id`, `candidate_ids: list[str]`, `selection: {summary, items:[{record_id, framing}]}`, `must_block: bool`.

**This gates the guards, not the model** (spec §10). No model call — the fixtures are synthetic stage-3 outputs. **Two-sided gate:** every `must_block` fixture must be blocked (100%), and every `must_pass` fixture (the collisions) must pass. A gate that could be satisfied by blocking everything reads green while Ask returns nothing — this branch has shipped exactly that failure before (`sanad-verify-dont-assert`).

Fixtures (spec §10 layer 1): fabricated record ID; real ID outside the candidate set; Arabic in a framing; Arabic in the summary; a grading claim; a unanimity claim; an over-length summary. Must-pass: a framing citing "Sahih al-Bukhari 2866"; a framing naming al-Ḥasan al-Baṣrī.

- [ ] **Step 1: Write the fixtures**

```json
// eval/cases/ask/adversarial.json
[
  {"id": "fabricated_id", "candidate_ids": ["quran:2:183"], "must_block": true,
   "selection": {"summary": "On fasting.",
     "items": [{"record_id": "quran:99:999", "framing": "A fabricated verse."}]}},
  {"id": "id_outside_candidates", "candidate_ids": ["quran:2:183"], "must_block": true,
   "selection": {"summary": "On fasting.",
     "items": [{"record_id": "hadith:bukhari:1", "framing": "Real id, not retrieved."}]}},
  {"id": "arabic_in_framing", "candidate_ids": ["quran:2:183"], "must_block": true,
   "selection": {"summary": "On fasting.",
     "items": [{"record_id": "quran:2:183", "framing": "It reads كتب عليكم الصيام."}]}},
  {"id": "arabic_in_summary", "candidate_ids": ["quran:2:183"], "must_block": true,
   "selection": {"summary": "The verse الصيام addresses fasting.",
     "items": [{"record_id": "quran:2:183", "framing": "Fasting is prescribed."}]}},
  {"id": "grading_claim", "candidate_ids": ["hadith:bukhari:2866"], "must_block": true,
   "selection": {"summary": "On striving.",
     "items": [{"record_id": "hadith:bukhari:2866", "framing": "This hadith is sahih."}]}},
  {"id": "unanimity_claim", "candidate_ids": ["quran:2:183"], "must_block": true,
   "selection": {"summary": "All scholars agree fasting is obligatory.",
     "items": [{"record_id": "quran:2:183", "framing": "Fasting is prescribed."}]}},
  {"id": "overlong_summary", "candidate_ids": ["quran:2:183"], "must_block": true,
   "selection": {"summary": "word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word",
     "items": [{"record_id": "quran:2:183", "framing": "Fasting is prescribed."}]}}
]
```

```json
// eval/cases/ask/must_pass.json
[
  {"id": "cite_sahih_al_bukhari", "candidate_ids": ["hadith:bukhari:2866"], "must_block": false,
   "selection": {"summary": "On striving in the path of God.",
     "items": [{"record_id": "hadith:bukhari:2866",
                "framing": "Reported in Sahih al-Bukhari 2866 on striving."}]}},
  {"id": "name_al_hasan_al_basri", "candidate_ids": ["hadith:bukhari:2866"], "must_block": false,
   "selection": {"summary": "On patience.",
     "items": [{"record_id": "hadith:bukhari:2866",
                "framing": "Narrated via al-Hasan al-Basri concerning patience."}]}}
]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/eval/test_ask_runner.py
from pathlib import Path
from eval.ask_runner import load_ask_cases, run_ask_gate

CASES = Path("eval/cases/ask")

def test_every_must_block_case_is_blocked():
    m = run_ask_gate(load_ask_cases(CASES))
    assert m.block_failures == [], m.block_failures

def test_every_must_pass_case_passes():
    m = run_ask_gate(load_ask_cases(CASES))
    assert m.pass_failures == [], m.pass_failures

def test_gate_counts_all_fixtures():
    m = run_ask_gate(load_ask_cases(CASES))
    assert m.total >= 9   # 7 adversarial + 2 collisions
```

- [ ] **Step 3: Run, confirm fail.**

- [ ] **Step 4: Implement the runner**

```python
# eval/ask_runner.py
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sanad.pipeline.guards import check
from sanad.pipeline.types import Selection, SelectedItem


@dataclass(frozen=True)
class AskCase:
    id: str
    candidate_ids: list[str]
    selection: Selection
    must_block: bool


@dataclass
class AskMetrics:
    total: int = 0
    passed: int = 0
    block_failures: list[str] = field(default_factory=list)   # should block, didn't
    pass_failures: list[str] = field(default_factory=list)     # should pass, blocked


def load_ask_cases(directory: Path) -> list[AskCase]:
    cases: list[AskCase] = []
    seen: set[str] = set()
    for path in sorted(Path(directory).glob("*.json")):
        for raw in json.loads(path.read_text(encoding="utf-8")):
            if raw["id"] in seen:
                raise ValueError(f"duplicate ask case id {raw['id']!r}")
            seen.add(raw["id"])
            sel = Selection(
                summary=raw["selection"]["summary"],
                items=[SelectedItem(i["record_id"], i["framing"])
                       for i in raw["selection"]["items"]])
            cases.append(AskCase(raw["id"], list(raw["candidate_ids"]),
                                 sel, bool(raw["must_block"])))
    return cases


def run_ask_gate(cases: list[AskCase]) -> AskMetrics:
    m = AskMetrics(total=len(cases))
    for c in cases:
        results = check(c.selection, set(c.candidate_ids))
        blocked = not all(g.passed for g in results)
        if c.must_block and not blocked:
            m.block_failures.append(c.id)
        elif not c.must_block and blocked:
            offenders = [g.name for g in results if not g.passed]
            m.pass_failures.append(f"{c.id} (blocked by {offenders})")
        else:
            m.passed += 1
    return m


def main(argv: list[str] | None = None) -> int:
    cases = load_ask_cases(Path("eval/cases/ask"))
    m = run_ask_gate(cases)
    print(f"ask cases {m.total}  passed {m.passed}")
    if m.block_failures:
        print(f"GATE FAILED: attacks that were NOT blocked: {m.block_failures}",
              file=sys.stderr)
    if m.pass_failures:
        print(f"GATE FAILED: correct briefs that WERE blocked: {m.pass_failures}",
              file=sys.stderr)
    return 1 if (m.block_failures or m.pass_failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run, confirm pass** — `pytest tests/eval/test_ask_runner.py -v` and `python eval/ask_runner.py`.

- [ ] **Step 6: Add the CI gate step** (`.github/workflows/ci.yml`, in the `test` job after the existing eval gate)

```yaml
      - name: Ask guard gate
        run: python eval/ask_runner.py
```

- [ ] **Step 7: Commit**

```bash
git add eval/cases/ask/ eval/ask_runner.py tests/eval/test_ask_runner.py .github/workflows/ci.yml
git commit -m "feat(eval): two-sided Ask guard gate — blocks attacks, passes collisions"
```

---

## Task 13: R46 — split `also_at` into `also_at` + `contained_in`

**Files:**
- Modify: `api/sanad/verify/engine.py` (`Match.contained_in`; stop merging disclosed ayat into `also_at`)
- Modify: `api/sanad/api/schemas.py` (`QuotationOut.contained_in`)
- Modify: `api/sanad/api/routes.py` (map the new field)
- Test: `tests/verify/test_engine.py` (extend)

**Interfaces:**
- `Match` gains `contained_in: list[str] = field(default_factory=list)`.
- `QuotationOut` gains `contained_in: list[str]`.

**Why (spec §8 "Debt paid here"; `sanad-ask-pipeline-plan-progress`):** `also_at` today conflates two relations — records with identical text at the matched tier, and the containing-āyah disclosure for a hadith (the F1 case). `IsnadTrace.tsx` currently distinguishes them only by the accident that the disclosure case has `record=None`. Splitting the field makes the contract explicit. The *frontend* consumption of `contained_in` belongs to the separate frontend plan; this task delivers the backend field and its rendering in the API.

The one behavioural change is in `engine._classify`'s hadith branch (`engine.py:570-578`): `disclosed` (the containing ayat) currently gets appended into `also_at` (line 578) and, in the withheld-verdict return (line 576-577), is passed in the `also_at` position. Move `disclosed` into `contained_in` and leave `also_at` for tied identical-text records only.

- [ ] **Step 1: Write the failing test** (the one shipped pair: Bukhari 3658 ⊂ Qur'an 54:1)

```python
# tests/verify/test_engine.py — add
def test_contained_in_carries_the_ayah_not_also_at(corpus_conn):
    # "the moon split" — hadith:bukhari:3658's matn sits inside Qur'an 54:1.
    matches = verify_spans(corpus_conn, "انشق القمر")
    m = matches[0]
    if m.record is not None and m.record.kind == "hadith":
        assert "quran:54:1" in m.contained_in
        assert "quran:54:1" not in m.also_at   # no longer conflated
```

(Use the existing `corpus_conn` fixture from the test module. If the exact needle/verdict differs on the shipped corpus, assert the invariant — `contained_in` holds the ayah, `also_at` does not — rather than a specific verdict.)

- [ ] **Step 2: Run, confirm fail** — `contained_in` attribute does not exist yet.

- [ ] **Step 3: Implement in `engine.py`**

Add the field to `Match`:

```python
    also_at: list[str] = field(default_factory=list)
    # Ayat whose own text CONTAINS this quotation, when the record reported is a
    # hadith (see `_ayat_containing`). Split out of `also_at` (R46): "these
    # words are also scripture at X" is a different relation from "these words
    # tie with record Y", and conflating them made the client tell them apart
    # only by the accident that the disclosure case has record=None.
    contained_in: list[str] = field(default_factory=list)
```

Change the hadith branch of `_classify` (currently lines ~570-580):

```python
    if record is not None and record.kind == "hadith":
        containing = _ayat_containing(conn, span.text, _WITHHOLDING_TIER)
        disclosed = [ayah.id for ayah in containing
                     if _contains_at(ayah, span.text, _DISCLOSURE_TIER)]
        if given is not None and any(not _reference_conflicts(given, ayah)
                                     for ayah in containing):
            return Match(span, Verdict.NOT_FOUND, None, None, 0.0, given, None,
                         also_at=[], contained_in=disclosed)
        return Match(span, verdict, record, tier, score, given, diff,
                     also_at=also_at, contained_in=disclosed)

    return Match(span, verdict, record, tier, score, given, diff, also_at=also_at)
```

- [ ] **Step 4: Map the field in `schemas.py` and `routes.py`**

```python
# schemas.py QuotationOut — add
    contained_in: list[str] = Field(default_factory=list)
```

```python
# routes.py verify() QuotationOut(...) — add
            contained_in=list(m.contained_in),
```

- [ ] **Step 5: Run the full verify suite, confirm pass**

Run: `pytest tests/verify/ -v`
Expected: PASS. Confirm no existing `also_at` assertion broke (the tied-record cases still use `also_at`; only the containing-ayah cases moved).

- [ ] **Step 6: Regenerate the client and commit**

```bash
cd web && npm run generate:client && cd ..
git add api/sanad/verify/engine.py api/sanad/api/schemas.py api/sanad/api/routes.py \
        tests/verify/test_engine.py web/src/api/types.ts
git commit -m "refactor(verify): split contained_in out of also_at (R46)"
```

---

## Documentation & final wiring

- [ ] **Step 1: Document Ask mode in README.md**

```markdown
### Ask mode (optional)

`POST /api/ask` returns an evidence brief — the passages in the corpus that
bear on a question, each verbatim and attributed. It needs an Anthropic key;
vector retrieval additionally needs a Voyage key and a prebuilt sidecar:

```
export ANTHROPIC_API_KEY=sk-ant-...
export VOYAGE_API_KEY=...                    # optional; lexical-only without it
sanad-ingest embed --db data/sanad-quran.db --vectors data/sanad-vectors.db
```

Without any key, `/api/verify` and the rest of the API work exactly as before —
Ask degrades to an abstention that says so. Claude never writes Arabic; the
server renders every quotation from the database by id, so a fabricated or
altered quotation cannot reach the screen.
```

- [ ] **Step 2: Update `docs/GAPS.md`** — note the two known limits carried from the spec (framing fairness has no hard guard; the public-demo Anthropic key spend cap is unresolved, spec §15) so they are refusals-of-record, not oversights.

- [ ] **Step 3: Run the whole suite and both gates**

```bash
ruff check api ingest eval
pytest -q
python eval/runner.py
python eval/ask_runner.py
cd web && npm run lint:types && npm test && cd ..
```

Expected: all green. (Note: `ruff check api ingest eval` currently fails on a pre-existing PIE810 in `api/sanad/api/app.py:41` per `sanad-ask-pipeline-plan-progress` — fix that one-liner in this pass since CI's Lint step is otherwise red: merge the three `path ==`/`.startswith()` checks into one `startswith(tuple)`.)

- [ ] **Step 4: Commit**

```bash
git add README.md docs/GAPS.md api/sanad/api/app.py
git commit -m "docs: document Ask mode; fix pre-existing PIE810 lint"
```

---

## Self-review

**1. Spec coverage.**
- §1 evidence-brief / structural safety → Tasks 7, 8, 11 (server renders by ID; no-Arabic guard).
- §2 seven stages → Task 10 (router, orchestration), 6 (expand), 4 (retrieve), 7 (select), 8 (check), 9 (audit, adjudicate).
- §3.1 one vector per record over full text → Task 3 `embed_text_for`.
- §3.2 model/quantization → Task 2; storage overridden to sidecar → Tasks 1, 3 (documented departure).
- §3.3 committed artifact / no key for build → Tasks 1, 3.
- §3.4 RRF → Task 4. §3.5 degradation → Tasks 4, 11. §3.6 reachability → Tasks 4, 10, 11.
- §4 response language / hadith framing-not-translation → Task 7 prompt.
- §5 guards → Task 8 (grading guard partial, collisions tested).
- §6 abstention success state / relevance floor / scope wording → Task 10.
- §7 API SSE + final payload + server-rendered record → Task 11.
- §8 frontend → **separate plan** (noted); R46 backend half → Task 13; `<mark title>` a11y → frontend plan.
- §9 audit log, no question text → Task 11.
- §10 eval (layer 1 gated, two-sided) → Task 12; layers 2/3 (recorded + live smoke) noted as follow-ups, not gated.
- §11 size ceiling (+1.7 MB binary) → Tasks 1–3; the derive-at-build-time fix stays Stage A3.
- §13 departures table → honored (no generated Arabic; seven stages; server render).
- §15 public demo key → GAPS note (docs step 2).

**2. Placeholder scan.** No "TBD"/"handle errors"/"similar to Task N" — every code step carries real code; every test step real asserts.

**3. Type consistency.** `RetrievalHit`/`RetrievalResult`/`Expansion`/`Selection`/`SelectedItem`/`GuardResult`/`AuditVerdict`/`StageEvent`/`Decision` are each defined once (`pipeline/types.py` + `adjudicate.py`) and referenced by the same names/fields in Tasks 4, 6–12. `call_structured` signature is identical across Tasks 5–9. `check(selection, candidate_ids)` and `adjudicate(*, guard_results, audit, risk_label, attempt)` match between definition (8, 9) and call site (10, 12).

**4. Review Focus coverage.** German/Spanish-no-key → Task 4 `test_no_key_and_no_lexical_reach_sets_unreached_reason` + Task 10 `test_no_candidates_abstains_with_scope`. ID outside candidates → Task 8 `test_blocks_id_outside_candidate_set` + Task 12. Arabic in prose → Task 8 (framing + summary) + Task 12. Collision must-pass → Task 8 (`Sahih al-Bukhari`, `al-Hasan al-Basri`) + Task 12 `must_pass.json`. Refusal / malformed → Task 5 (`test_refusal_raises_claude_error`) + Task 10 (`test_claude_error_in_expand_abstains_not_raises`).

**Known amendments carried forward:**
- Stages import `claude_client` module-qualified (Tasks 6, 7, 9) so Task 12/monkeypatch interception works.
- Voyage response shape is pinned but unverified — Task 3 Step 5 is the first live check.
- Task 13's needle/verdict may shift on the shipped corpus; assert the invariant, not a literal verdict.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-24-ask-pipeline.md`. Backend only; the frontend is a separate follow-up plan.


