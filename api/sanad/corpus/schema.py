"""Corpus DDL. Stage A creates the full spec schema so Stage B needs no migration.

`audit_log` is deliberately NOT in `SCHEMA_SQL` -- see `AUDIT_SCHEMA_SQL` below.
The corpus database is shipped, content-addressed data: its SHA-256 is meant
to be a stable, reproducible fact ("rebuild from the lockfile, hash it,
compare"). A table that every `/api/verify` request writes to cannot live in
that same file without making the hash drift the moment the product is
used -- which is exactly what an earlier revision of this schema did, and
Task 11 corrected by giving the audit log its own database. See
`api/sanad/settings.resolve_audit_db_path` and `api/sanad/api/app.py`.
"""

SOURCE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sources (
  id              TEXT PRIMARY KEY,
  kind            TEXT NOT NULL,
  title           TEXT NOT NULL,
  publisher       TEXT,
  edition         TEXT,
  url             TEXT NOT NULL,
  license_id      TEXT NOT NULL,
  license_url     TEXT,
  attribution     TEXT NOT NULL,
  retrieved_at    TEXT NOT NULL,
  upstream_sha256 TEXT NOT NULL,
  modifications   TEXT NOT NULL
);

-- text_ar_sha256, norm_light, norm_standard and norm_aggressive carry NO
-- `NOT NULL` here, even though every row `build_corpus` ever writes
-- populates all four: a source-only DB (Stage A3) commits `records` with
-- these DERIVED columns unpopulated -- `materialize()` fills them in, and
-- `_assert_complete` there is the real completeness gate, not this
-- constraint. `text_ar` keeps `NOT NULL`: it is the canonical Arabic matn, a
-- SOURCE column that is never stripped and must never be null -- the same
-- invariant `build.py`'s "empty scored text" check enforces at build time.
-- `reference_display` also keeps `NOT NULL`: it is a committed source column
-- at every stage (see Stage A3 ruling R-A3-3, `sanad_ingest.materialize`
-- docstring), never blanked and never derived here.
CREATE TABLE IF NOT EXISTS records (
  id                TEXT PRIMARY KEY,
  source_id         TEXT NOT NULL REFERENCES sources(id),
  kind              TEXT NOT NULL,
  surah             INTEGER,
  ayah              INTEGER,
  surah_name_ar     TEXT,
  surah_name_en     TEXT,
  collection        TEXT,
  book_no           INTEGER,
  chapter_ar        TEXT,
  hadith_no         TEXT,
  numbering_scheme  TEXT,
  text_ar           TEXT NOT NULL,
  text_ar_sha256    TEXT,
  bismillah         TEXT,
  isnad_ar          TEXT,
  addenda_ar        TEXT,
  unscorable_reason TEXT,
  norm_light        TEXT,
  norm_standard     TEXT,
  norm_aggressive   TEXT,
  reference_display TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS translations (
  record_id TEXT NOT NULL REFERENCES records(id),
  source_id TEXT NOT NULL REFERENCES sources(id),
  lang      TEXT NOT NULL,
  text      TEXT NOT NULL,
  PRIMARY KEY (record_id, source_id)
);

CREATE TABLE IF NOT EXISTS gradings (
  record_id    TEXT NOT NULL REFERENCES records(id),
  authority    TEXT NOT NULL,
  grade        TEXT NOT NULL,
  is_classical INTEGER NOT NULL,
  source_id    TEXT NOT NULL REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS embeddings (
  record_id TEXT PRIMARY KEY REFERENCES records(id),
  model     TEXT NOT NULL,
  dim       INTEGER NOT NULL,
  vec       BLOB NOT NULL
);
"""

# Everything a source-only DB does NOT carry: the norm_*/reference_display
# columns already live on `records` (Stage A3 keeps that table's shape
# unchanged; only their values are stripped before commit), but the indexes
# over them, the `record_variants` table, and the FTS index are all fully
# recomputable from source columns, so they are re-created by
# `sanad_ingest.materialize.materialize` rather than committed. See
# `db.DERIVED_SCHEMA_SQL` call sites and the Stage A3 plan.
DERIVED_SCHEMA_SQL = """
CREATE INDEX IF NOT EXISTS idx_records_ref ON records(surah, ayah);

-- Additional scorable representations of a record's text. One row per
-- representation BEYOND records.text_ar -- today exactly one kind, 'full'
-- (the primary matn with its addenda rejoined), on the hadith records that
-- carry an addendum. See corpus.models.RecordVariant for why both sides of
-- the secondary-narration cut have to be scored.
CREATE TABLE IF NOT EXISTS record_variants (
  record_id       TEXT NOT NULL REFERENCES records(id),
  variant         TEXT NOT NULL,
  text_ar         TEXT NOT NULL,
  norm_light      TEXT NOT NULL,
  norm_standard   TEXT NOT NULL,
  norm_aggressive TEXT NOT NULL,
  PRIMARY KEY (record_id, variant)
);

-- Maps each FTS5 rowid to its (record_id, variant) so that MATCH results can
-- be joined back to `records` and `record_variants`. Needed because contentless
-- FTS5 (content="") does not store column values -- it stores only the
-- inverted token index and exposes nothing but `rowid` after a MATCH.
CREATE TABLE IF NOT EXISTS fts_rowid_map (
  rowid     INTEGER PRIMARY KEY,
  record_id TEXT NOT NULL,
  variant   TEXT NOT NULL
);

-- Contentless FTS5: the inverted token index only -- no duplicate copy of
-- norm/translation text already in `records` and `record_variants`. Saves
-- ~30 MB vs the content-bearing form. rowid of each row matches the
-- corresponding row in fts_rowid_map, enabling the join after a MATCH.
CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
  norm_standard,
  norm_aggressive,
  translation,
  tokenize = "unicode61 remove_diacritics 2",
  content = ""
);
"""

# Byte-for-byte identical to the pre-split schema: every importer that ran
# `conn.executescript(SCHEMA_SQL)` (db.py:31 among them) must see the exact
# same DDL, in the exact same order, whether or not it knows about the
# source/derived split.
SCHEMA_SQL = SOURCE_SCHEMA_SQL + DERIVED_SCHEMA_SQL

# The audit log's own schema, for its own database file (never the corpus
# file). Table shape is unchanged from the original single-file design.
AUDIT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
  id          INTEGER PRIMARY KEY,
  ts          TEXT NOT NULL,
  request_id  TEXT NOT NULL,
  stage       TEXT NOT NULL,
  verdict     TEXT NOT NULL,
  detail_json TEXT NOT NULL
);
"""
