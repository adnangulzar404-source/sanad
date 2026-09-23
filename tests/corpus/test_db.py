from dataclasses import replace

import pytest
from sanad.corpus import db
from sanad.corpus.models import Record, RecordVariant, Source

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
    assert [h.record.id for h in hits] == ["quran:112:2"]
    assert [h.variant for h in hits] == ["primary"]


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


def _a_source(id: str = SRC.id, kind: str = SRC.kind) -> Source:
    # Mirrors SRC above, but lets callers pick the id/kind, since the
    # isnad tests below need a hadith-shaped source rather than the
    # quran-arabic one used everywhere else in this file.
    return Source(
        id=id, kind=kind, title="Tanzil Uthmani",
        publisher="Tanzil Project", edition="1.1", url="https://tanzil.net/",
        license_id="CC-BY-3.0", license_url="https://tanzil.net/docs/text_license",
        attribution="# Tanzil copyright block", retrieved_at="2026-09-19",
        upstream_sha256="deadbeef", modifications="none",
    )


def _an_ayah(id: str = "quran:112:1") -> Record:
    return _rec(id, 112, 1, "قل هو الله احد")


def test_round_trips_a_hadith_record_with_its_isnad(tmp_path):
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, _a_source(id="openiti-bukhari-jk000110", kind="hadith-arabic"))
    rec = Record(
        id="hadith:bukhari:1",
        source_id="openiti-bukhari-jk000110",
        kind="hadith",
        collection="bukhari",
        hadith_no="1",
        numbering_scheme="bugha-1987",
        text_ar="MATN",
        isnad_ar="ISNAD",
        text_ar_sha256="x" * 64,
        norm_light="MATN", norm_standard="MATN", norm_aggressive="MATN",
        reference_display="Sahih al-Bukhari 1",
    )
    db.insert_records(conn, [rec])
    got = db.get_record(conn, "hadith:bukhari:1")
    assert got.isnad_ar == "ISNAD"
    assert got.text_ar == "MATN"
    assert got.surah is None and got.ayah is None


def test_quran_records_have_no_isnad(tmp_path):
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, _a_source())
    db.insert_records(conn, [_an_ayah(id="quran:112:1")])
    assert db.get_record(conn, "quran:112:1").isnad_ar is None


def test_round_trips_a_hadith_record_with_its_addenda(tmp_path):
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, _a_source(id="openiti-bukhari-jk000110", kind="hadith-arabic"))
    rec = Record(
        id="hadith:bukhari:1",
        source_id="openiti-bukhari-jk000110",
        kind="hadith",
        collection="bukhari",
        hadith_no="1",
        numbering_scheme="bugha-1987",
        text_ar="MATN",
        isnad_ar="ISNAD",
        addenda_ar="ADDENDA",
        text_ar_sha256="x" * 64,
        norm_light="MATN", norm_standard="MATN", norm_aggressive="MATN",
        reference_display="Sahih al-Bukhari 1",
    )
    db.insert_records(conn, [rec])
    got = db.get_record(conn, "hadith:bukhari:1")
    assert got.addenda_ar == "ADDENDA"
    assert got.text_ar == "MATN"
    assert got.isnad_ar == "ISNAD"


def test_quran_records_have_no_addenda(tmp_path):
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, _a_source())
    db.insert_records(conn, [_an_ayah(id="quran:112:1")])
    assert db.get_record(conn, "quran:112:1").addenda_ar is None


def _a_hadith_record() -> Record:
    return Record(
        id="hadith:bukhari:1", source_id="openiti-bukhari-jk000110", kind="hadith",
        collection="bukhari", hadith_no="1", numbering_scheme="bugha-1987",
        text_ar="matnword", isnad_ar="isnadword", addenda_ar="addendaword",
        text_ar_sha256="x" * 64, norm_light="matnword",
        norm_standard="matnword", norm_aggressive="matnword",
        reference_display="Sahih al-Bukhari 1")


def test_the_fts_index_never_sees_the_isnad(tmp_path):
    """The chain is absent from the index by construction.

    Exhaustive on content, not on one probe term: the index is rebuilt from a
    record whose isnad is a string that appears nowhere else, and the whole
    index is then searched for it.

    The addenda are a different case since round 5 and are checked in the
    test below: they are indexed, but only as part of the record's full
    printed text, never on their own and never inside the primary's norms.
    """
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, _a_source(id="openiti-bukhari-jk000110", kind="hadith-arabic"))
    db.insert_records(conn, [_a_hadith_record()])
    db.rebuild_fts(conn)
    indexed = " ".join(
        f"{r['norm_standard']} {r['norm_aggressive']} {r['translation']}"
        for r in conn.execute(
            "SELECT norm_standard, norm_aggressive, translation FROM records_fts"))
    assert "matnword" in indexed, "the matn must be searchable"
    assert "isnadword" not in indexed


def test_an_addendum_is_indexed_only_as_part_of_the_full_text(tmp_path):
    """Two index rows, and the addendum appears in exactly one of them.

    The round-5 change: the full printed text is scored alongside the primary
    matn, so a quotation of the hadith as the edition prints it verifies. What
    must NOT happen is the addendum leaking into the primary's row, which
    would put a 40%-longer string behind a quotation of the Prophet's words
    alone -- the defect rounds 1-3 existed to fix.
    """
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, _a_source(id="openiti-bukhari-jk000110", kind="hadith-arabic"))
    db.insert_records(conn, [_a_hadith_record()])
    db.insert_record_variants(conn, [RecordVariant(
        record_id="hadith:bukhari:1", variant="full",
        text_ar="matnword addendaword", norm_light="matnword addendaword",
        norm_standard="matnword addendaword",
        norm_aggressive="matnword addendaword")])
    db.rebuild_fts(conn)
    rows = {r["variant"]: f"{r['norm_standard']} {r['norm_aggressive']}"
            for r in conn.execute(
                "SELECT variant, norm_standard, norm_aggressive FROM records_fts")}
    assert set(rows) == {"primary", "full"}
    assert "addendaword" not in rows["primary"]
    assert "addendaword" in rows["full"]
    assert "isnadword" not in " ".join(rows.values())


def test_a_record_indexed_twice_is_still_one_search_result(tmp_path):
    """`fts_records` collapses the representations; `fts_candidates` does not.

    Without the collapse the same hadith is listed twice in `GET /api/search`
    -- once per representation -- for no reason a reader could understand.
    """
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, _a_source(id="openiti-bukhari-jk000110", kind="hadith-arabic"))
    db.insert_records(conn, [_a_hadith_record()])
    db.insert_record_variants(conn, [RecordVariant(
        record_id="hadith:bukhari:1", variant="full",
        text_ar="matnword addendaword", norm_light="matnword addendaword",
        norm_standard="matnword addendaword",
        norm_aggressive="matnword addendaword")])
    db.rebuild_fts(conn)
    assert len(db.fts_candidates(conn, "matnword")) == 2
    assert [r.id for r in db.fts_records(conn, "matnword")] == ["hadith:bukhari:1"]


def test_a_candidate_carries_the_text_that_was_indexed(tmp_path):
    """Not the record's own `text_ar`.

    `_best_fuzzy` scores whatever this returns. Handing it the primary matn
    for a hit on the full text would report a similarity the index never
    found, and would build the displayed diff against the wrong string.
    """
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, _a_source(id="openiti-bukhari-jk000110", kind="hadith-arabic"))
    db.insert_records(conn, [_a_hadith_record()])
    db.insert_record_variants(conn, [RecordVariant(
        record_id="hadith:bukhari:1", variant="full",
        text_ar="matnword addendaword", norm_light="matnword addendaword",
        norm_standard="matnword addendaword",
        norm_aggressive="matnword addendaword")])
    db.rebuild_fts(conn)
    by_variant = {c.variant: c for c in db.fts_candidates(conn, "matnword")}
    assert by_variant["primary"].text_ar == "matnword"
    assert by_variant["primary"].norm_aggressive == "matnword"
    assert by_variant["full"].text_ar == "matnword addendaword"
    assert by_variant["full"].norm_aggressive == "matnword addendaword"


def test_an_excluded_records_second_representation_is_indexed(tmp_path):
    """`unscorable_reason` excludes the primary row, and only that row.

    This test asserted the opposite until the whole-branch review, and the
    code, the docstrings and the test agreed with each other while being
    wrong together. The reason is a judgement about ONE string -- the primary
    matn, pinned by its sha256 in the ingest audit -- and the full printed
    text is a different string that was never judged. Hadith 237 is the one
    record in this edition where the two differ: a 40-character
    chain-transfer fragment, and behind it the longest narration in the
    collection at 869 characters, which the old rule removed from the corpus
    entirely.

    The primary stays excluded, which is the half that was always right: an
    editorial pointer answered as a hadith is how "bi-hadha" once returned
    EXACT 1.0 / Sahih al-Bukhari 1379.
    """
    conn = db.connect(tmp_path / "c.db", read_only=False)
    db.insert_source(conn, _a_source(id="openiti-bukhari-jk000110", kind="hadith-arabic"))
    rec = _a_hadith_record()
    db.insert_records(conn, [replace(rec, unscorable_reason="chapter-heading")])
    db.insert_record_variants(conn, [RecordVariant(
        record_id="hadith:bukhari:1", variant="full",
        text_ar="matnword addendaword", norm_light="matnword addendaword",
        norm_standard="matnword addendaword",
        norm_aggressive="matnword addendaword")])
    db.rebuild_fts(conn)
    indexed = conn.execute(
        "SELECT variant FROM records_fts").fetchall()
    assert [r["variant"] for r in indexed] == ["full"]
    # the full text is a candidate; the primary is not
    assert {c.variant for c in db.fts_candidates(conn, "addendaword")} == {"full"}
    assert db.fts_records(conn, "addendaword") != []
    # still stored, still fetchable, still displayable
    assert db.get_record(conn, "hadith:bukhari:1") is not None
    assert len(db.get_record_variants(conn, "hadith:bukhari:1")) == 1


def test_no_scoring_code_reads_the_display_only_columns():
    """Structural guard, in the spirit of the isnad_ar rule Task 3 set.

    A data test can only show that today's corpus happens not to leak; this
    shows that no code path in the verify engine can reach either column at
    all -- scoring is the one place a display-only column must never surface,
    because scoring it changes verdicts.

    Both `isnad_ar` and `addenda_ar` are checked only against the engine, not
    against the HTTP routes or schemas: Round 5 put `addenda_ar` on purpose
    into `RecordOut`, and Task 7 did the same for `isnad_ar` -- both were
    stored and unreachable, which made "nothing is discarded" true of the
    database and false of the product -- so routes and schemas now name both
    columns deliberately. The engine still must not read either: it scores
    `record_variants`, where the build has already rejoined `text_ar` and
    `addenda_ar`, and an engine that concatenated the columns itself would be
    a second, divergent definition of what the full text is; scoring
    `isnad_ar` at all is the Stage A2 spec sec 7 defect this guard exists to
    keep fixed -- a short, famous matn plus its narrator chain drops well
    under the 0.86 threshold.
    """
    from pathlib import Path
    engine = Path("api/sanad/verify/engine.py").read_text(encoding="utf-8")
    assert "isnad_ar" not in engine, "the engine must not score the narrator chain"
    assert "addenda_ar" not in engine, "the engine must not assemble the full text"


def test_rebuild_fts_selects_only_the_norm_columns():
    """The FTS insert is the one place a display-only column could leak into
    the index. Pin its SELECT list rather than trusting a probe string."""
    import inspect
    source = inspect.getsource(db.rebuild_fts)
    assert "addenda_ar" not in source
    assert "isnad_ar" not in source
    assert "text_ar" not in source


# --- the fingerprint CI compares a fresh build against -----------------------
#
# F5: the CI step's own fingerprint was `sha256` over `(records.id,
# records.text_ar_sha256)`. The I1 fix changed `record_variants` and
# `records_fts` and changed no `records` row, so deleting hadith 237's variant
# and index rows left that fingerprint byte-identical. pytest caught the
# mutation; the step whose whole job is to catch it did not. Its comment said
# "the comparison is over CONTENT, not row counts", which a reader takes as
# covering the corpus, and it covered one table.
#
# The fingerprint now lives here rather than inline in ci.yml, so it is code
# with tests rather than a YAML heredoc nobody runs.


def _rows_of(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_the_fingerprint_is_stable_for_an_unchanged_database(conn):
    assert db.corpus_fingerprint(conn) == db.corpus_fingerprint(conn)


def test_deleting_a_variant_row_changes_the_fingerprint(tmp_path):
    """The exact mutation the re-review used. `record_variants` holds the
    second scorable representation of a cut hadith; losing one takes a real
    printed narration out of the corpus and touches no `records` row."""
    c = db.connect(tmp_path / "t.db", read_only=False)
    db.insert_source(c, SRC)
    db.insert_records(c, [_rec("quran:112:1", 112, 1, "قل هو الله احد")])
    db.insert_record_variants(c, [RecordVariant(
        record_id="quran:112:1", variant="full", text_ar="x",
        norm_light="x", norm_standard="x", norm_aggressive="x")])
    db.rebuild_fts(c)
    before = db.corpus_fingerprint(c)
    c.execute("DELETE FROM record_variants WHERE variant = 'full'")
    c.commit()
    assert _rows_of(c, "record_variants") == 0
    assert db.corpus_fingerprint(c) != before


def test_deleting_an_index_row_changes_the_fingerprint(conn):
    """`records_fts` is derived from the other tables, which is exactly why
    it has to be in the comparison: a build that wrote the records correctly
    and indexed them wrongly puts them out of reach of every tier, and every
    row of `records` still matches."""
    before = db.corpus_fingerprint(conn)
    conn.execute("DELETE FROM records_fts WHERE record_id = 'quran:112:1'")
    conn.commit()
    assert db.corpus_fingerprint(conn) != before


def test_changing_a_norm_column_changes_the_fingerprint(conn):
    """`text_ar_sha256` alone cannot see this: the norms are what the tiers
    actually compare, and a normalizer change rewrites them while every
    stored text stays byte-identical."""
    before = db.corpus_fingerprint(conn)
    conn.execute("UPDATE records SET norm_aggressive = norm_aggressive || 'x'"
                 " WHERE id = 'quran:112:1'")
    conn.commit()
    assert db.corpus_fingerprint(conn) != before


def test_the_retrieval_DATE_is_the_one_thing_the_fingerprint_ignores(conn):
    """A rebuild happens on a different day from the committed build, and
    `sources.retrieved_at` records the day. Including it would make the CI
    step fail every day for no reason, so it is excluded -- and it is the
    ONLY exclusion: the licence, the attribution and the upstream sha256 in
    the same row are all compared."""
    before = db.corpus_fingerprint(conn)
    conn.execute("UPDATE sources SET retrieved_at = '1999-01-01'")
    conn.commit()
    assert db.corpus_fingerprint(conn) == before
    conn.execute("UPDATE sources SET license_id = 'something-else'")
    conn.commit()
    assert db.corpus_fingerprint(conn) != before


def test_the_fingerprint_covers_every_table_the_build_writes():
    """The guard against this narrowing happening again. Any table declared
    in the schema that the shipped corpus actually has rows in must be in the
    fingerprint; a new table added to the build and not here would otherwise
    go uncompared in silence, which is what F5 was.
    """
    import re

    from sanad.corpus.schema import SCHEMA_SQL
    declared = re.findall(r"CREATE (?:VIRTUAL )?TABLE IF NOT EXISTS (\w+)",
                          SCHEMA_SQL)
    assert len(declared) >= 6, declared
    conn = db.connect("data/sanad-quran.db")
    populated = {t for t in declared if _rows_of(conn, t)}
    covered = {t for t, _cols, _order in db.FINGERPRINT_TABLES}
    assert populated - covered == set(), populated - covered
    assert covered - populated == set(), covered - populated


def _one_record_db(tmp_path, name, **overrides):
    c = db.connect(tmp_path / name, read_only=False)
    db.insert_source(c, SRC)
    db.insert_records(c, [replace(_rec("quran:112:1", 112, 1, "قل هو الله احد"),
                                  **overrides)])
    db.rebuild_fts(c)
    return c


def test_an_empty_column_and_an_absent_one_do_not_hash_alike(tmp_path):
    """A record with no addendum and a record with an empty-string addendum
    are different content, and a fingerprint that flattens both to "" would
    call a build that lost every NULL identical to the one that kept them.
    The stand-in for NULL is a control character no corpus text contains, so
    it cannot be forged by the text either."""
    absent = _one_record_db(tmp_path, "a.db", addenda_ar=None)
    empty = _one_record_db(tmp_path, "b.db", addenda_ar="")
    assert db.corpus_fingerprint(absent) != db.corpus_fingerprint(empty)


def test_content_moved_across_a_column_boundary_changes_the_fingerprint(tmp_path):
    """The field separator, pinned. Concatenating the columns without one
    makes ("ab", "c") and ("a", "bc") the same string, so a build that wrote
    the surah's Arabic name into its English name would hash identically."""
    split_one = _one_record_db(tmp_path, "c.db", surah_name_ar="ab",
                               surah_name_en="c")
    split_two = _one_record_db(tmp_path, "d.db", surah_name_ar="a",
                               surah_name_en="bc")
    assert db.corpus_fingerprint(split_one) != db.corpus_fingerprint(split_two)
