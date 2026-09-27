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

-- text_ar, text_ar_sha256, norm_light, norm_standard and norm_aggressive
-- carry NO `NOT NULL` here, even though every row `build_corpus` ever writes
-- populates all five: a source-only DB (Stage A3) commits `records` with the
-- three norm_* columns and text_ar_sha256 unpopulated -- `materialize()`
-- fills them in, and `_assert_complete` there is the real completeness gate,
-- not this constraint. `text_ar` is nullable for the same reason
-- `materialize`'s own test suite needs it to be: a record whose canonical
-- text a source-only DB failed to carry must be representable as a row
-- (NULL), so that failure can be asserted on with a real query rather than
-- constructed out of reach. `reference_display` is the one column of this
-- group that keeps `NOT NULL`: it is a committed source column at every
-- stage (see Stage A3 ruling R-A3-3, `sanad_ingest.materialize` docstring),
-- never blanked and never derived here.
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
  text_ar           TEXT,
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
CREATE INDEX IF NOT EXISTS idx_records_norm_std ON records(norm_standard);
CREATE INDEX IF NOT EXISTS idx_records_norm_light ON records(norm_light);

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

CREATE INDEX IF NOT EXISTS idx_variants_norm_light ON record_variants(norm_light);
CREATE INDEX IF NOT EXISTS idx_variants_norm_std ON record_variants(norm_standard);

-- One row per SCORABLE REPRESENTATION, not one row per record: a record with
-- an addendum has two (see record_variants). `variant` names which one, so a
-- hit can be scored against the text that was actually indexed rather than
-- against whatever happens to be in records.text_ar.
CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
  record_id UNINDEXED,
  variant UNINDEXED,
  norm_standard,
  norm_aggressive,
  translation,
  tokenize = "unicode61 remove_diacritics 2"
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
