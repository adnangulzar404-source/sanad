import hashlib
import re
import sqlite3
from pathlib import Path

import pytest
from sanad.arabic.normalize import normalize
from sanad.corpus import db
from sanad_ingest.build import build_corpus
from sanad_ingest.lockfile import LockedSource
from sanad_ingest.materialize import MaterializeError, materialize

FIXTURE = Path("tests/fixtures/tanzil_excerpt.txt")
XML_FIXTURE = Path("tests/fixtures/tanzil_excerpt.xml")
TRANSLATION_FIXTURE = Path("tests/fixtures/pickthall_excerpt.txt")


def _payload_sha256(raw: str) -> str:
    payload = "\n".join(
        l for l in raw.split("\n") if l.strip() and not l.strip().startswith("#"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@pytest.fixture()
def built(tmp_path, monkeypatch):
    raw = FIXTURE.read_text(encoding="utf-8")
    payload = "\n".join(
        l for l in raw.split("\n") if l.strip() and not l.strip().startswith("#"))
    sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    lock = tmp_path / "corpus.lock.toml"
    lock.write_text(
        'lockfile_version = 1\n[[source]]\n'
        'id = "tanzil-uthmani-1.1"\nkind = "quran-arabic"\nformat = "txt-2"\n'
        'title = "Tanzil Uthmani"\npublisher = "Tanzil Project"\n'
        'edition = "1.1"\nurl = "https://example.invalid/q"\n'
        'license_id = "CC-BY-3.0"\nlicense_url = "https://tanzil.net/docs/text_license"\n'
        f'content_sha256 = "{sha}"\nexpected_lines = 4\nmodifications = "none"\n',
        encoding="utf-8")

    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: raw)
    out = tmp_path / "sanad.db"
    stats = build_corpus(lock, out, tmp_path / "cache")
    return out, stats


def test_builds_expected_record_count(built):
    _, stats = built
    assert stats["records"] == 4


def test_canonical_text_is_stored_unmodified(built):
    out, _ = built
    conn = db.connect(out)
    rec = db.get_record(conn, "quran:112:1")
    assert rec.text_ar == "قُلْ هُوَ ٱللَّهُ أَحَدٌ"  # diacritics and wasla intact


def test_build_output_is_source_only(built):
    # Stage A3 Task 4: `build` emits a SOURCE-ONLY DB -- no derived tables, no
    # derived columns -- while the source columns (text_ar, reference_display)
    # are fully populated. materialize() is what derives the rest.
    out, _ = built
    c = sqlite3.connect(out)
    assert c.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='records_fts'"
    ).fetchone()[0] == 0
    assert c.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='record_variants'"
    ).fetchone()[0] == 0
    assert c.execute(
        "SELECT COUNT(*) FROM records WHERE norm_standard IS NOT NULL"
    ).fetchone()[0] == 0
    assert c.execute(
        "SELECT COUNT(*) FROM records WHERE text_ar_sha256 IS NOT NULL"
    ).fetchone()[0] == 0
    # Source columns are still there.
    assert c.execute(
        "SELECT COUNT(*) FROM records WHERE text_ar IS NULL"
    ).fetchone()[0] == 0
    assert c.execute(
        "SELECT COUNT(*) FROM records WHERE reference_display IS NULL"
    ).fetchone()[0] == 0


def test_norm_columns_are_null_in_source_only(built):
    out, _ = built
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.norm_standard is None
    assert rec.norm_light is None
    assert rec.norm_aggressive is None


def test_text_checksum_is_null_in_source_only(built):
    out, _ = built
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.text_ar_sha256 is None


def test_attribution_block_is_stored_verbatim(built):
    out, _ = built
    row = db.connect(out).execute(
        "SELECT attribution FROM sources WHERE id='tanzil-uthmani-1.1'").fetchone()
    assert "PLEASE DO NOT REMOVE" in row["attribution"]


def test_reference_display_uses_surah_name(built):
    out, _ = built
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.reference_display == "Al-Ikhlas 112:1"


def test_fts_table_is_absent_in_source_only(built):
    # records_fts is a derived table; the source-only build never creates it.
    out, _ = built
    assert sqlite3.connect(out).execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='records_fts'"
    ).fetchone()[0] == 0


def test_build_succeeds_with_arabic_only_lockfile(built):
    # Stage A must not become dependent on the translation: a lockfile with
    # only the Arabic source still builds, with zero translation rows.
    out, stats = built
    assert stats["records"] == 4
    assert stats["translations"] == 0
    conn = db.connect(out)
    assert conn.execute("SELECT count(*) FROM translations").fetchone()[0] == 0


# --- Two-source build: Arabic + Pickthall English translation --------------

_ARABIC_URL = "https://example.invalid/q"
_TRANSLATION_URL = "https://example.invalid/trans"


@pytest.fixture()
def built_with_translation(tmp_path, monkeypatch):
    raw_ar = FIXTURE.read_text(encoding="utf-8")
    sha_ar = _payload_sha256(raw_ar)

    raw_en = TRANSLATION_FIXTURE.read_text(encoding="utf-8")
    sha_en = _payload_sha256(raw_en)

    lock = tmp_path / "corpus.lock.toml"
    lock.write_text(
        'lockfile_version = 1\n'
        '[[source]]\n'
        'id = "tanzil-uthmani-1.1"\nkind = "quran-arabic"\nformat = "txt-2"\n'
        'title = "Tanzil Uthmani"\npublisher = "Tanzil Project"\n'
        'edition = "1.1"\n'
        f'url = "{_ARABIC_URL}"\n'
        'license_id = "CC-BY-3.0"\nlicense_url = "https://tanzil.net/docs/text_license"\n'
        f'content_sha256 = "{sha_ar}"\nexpected_lines = 4\nmodifications = "none"\n'
        '\n'
        '[[source]]\n'
        'id = "tanzil-en-pickthall"\nkind = "quran-translation"\nformat = "txt-2"\n'
        'title = "The Meaning of the Glorious Koran (Pickthall)"\n'
        'publisher = "Tanzil Project (distribution)"\n'
        'edition = "en.pickthall"\n'
        f'url = "{_TRANSLATION_URL}"\n'
        'license_id = "public-domain"\nlicense_url = "https://tanzil.net/trans/"\n'
        f'content_sha256 = "{sha_en}"\nexpected_lines = 4\nmodifications = "none"\n',
        encoding="utf-8")

    raws = {_ARABIC_URL: raw_ar, _TRANSLATION_URL: raw_en}
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: raws[url])
    out = tmp_path / "sanad.db"
    stats = build_corpus(lock, out, tmp_path / "cache")
    return out, stats


def test_translation_rows_are_populated(built_with_translation):
    out, stats = built_with_translation
    assert stats["translations"] == 4
    conn = db.connect(out)
    assert conn.execute("SELECT count(*) FROM translations").fetchone()[0] == 4


def test_translation_text_is_stored_verbatim(built_with_translation):
    out, _ = built_with_translation
    conn = db.connect(out)
    row = conn.execute(
        "SELECT text FROM translations WHERE record_id='quran:112:1' "
        "AND source_id='tanzil-en-pickthall'").fetchone()
    assert row["text"] == "Say: He is Allah, the One!"


def test_translation_source_records_public_domain_licence(built_with_translation):
    out, _ = built_with_translation
    row = db.connect(out).execute(
        "SELECT license_id FROM sources WHERE id='tanzil-en-pickthall'").fetchone()
    assert row["license_id"] == "public-domain"


def test_translation_attribution_is_captured(built_with_translation):
    out, _ = built_with_translation
    row = db.connect(out).execute(
        "SELECT attribution FROM sources WHERE id='tanzil-en-pickthall'").fetchone()
    assert row["attribution"].strip() != ""


def test_translation_source_build_is_still_source_only(built_with_translation):
    # The FTS index over translation text is derived in materialize(), not
    # build; the source-only build with a translation source still emits no
    # records_fts. (test_materialize covers that the index picks up
    # translations.)
    out, _ = built_with_translation
    assert sqlite3.connect(out).execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='records_fts'"
    ).fetchone()[0] == 0


# --- Arabic source via the XML export (bismillah as metadata) --------------
#
# txt-2 prepends the Bismillah to ayah 1's text for every surah except
# At-Tawbah, corrupting text_ar. These tests build from the XML export
# fixture and confirm build_corpus keeps text_ar and bismillah separate --
# independent of the committed database (see tests/ingest/test_real_corpus.py
# for the equivalent checks against data/sanad-quran.db itself).

_TAG = re.compile(r'<sura index="(\d+)"|<aya index="(\d+)" text="([^"]*)"')


def _xml_payload_sha256(raw: str) -> str:
    # Deliberately reimplemented with plain regex, not by calling
    # parse_tanzil_xml, so this fixture doesn't just check the parser
    # against itself. Scans tag-by-tag in document order (not line-by-line)
    # so it doesn't care whether a fixture puts one tag per line or several
    # tags on one line.
    surah = None
    lines = []
    for m in _TAG.finditer(raw):
        sura_index, aya_index, aya_text = m.groups()
        if sura_index is not None:
            surah = int(sura_index)
        elif surah is not None:
            lines.append(f"{surah}|{int(aya_index)}|{aya_text}")
    payload = "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_XML_ARABIC_URL = "https://example.invalid/xml-q"


@pytest.fixture()
def built_from_xml(tmp_path, monkeypatch):
    raw = XML_FIXTURE.read_text(encoding="utf-8")
    sha = _xml_payload_sha256(raw)

    lock = tmp_path / "corpus.lock.toml"
    lock.write_text(
        'lockfile_version = 1\n[[source]]\n'
        'id = "tanzil-uthmani-1.1"\nkind = "quran-arabic"\nformat = "xml"\n'
        'title = "Tanzil Uthmani"\npublisher = "Tanzil Project"\n'
        'edition = "1.1"\n'
        f'url = "{_XML_ARABIC_URL}"\n'
        'license_id = "CC-BY-3.0"\nlicense_url = "https://tanzil.net/docs/text_license"\n'
        f'content_sha256 = "{sha}"\nexpected_lines = 4\nmodifications = "none"\n',
        encoding="utf-8")

    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: raw)
    out = tmp_path / "sanad.db"
    stats = build_corpus(lock, out, tmp_path / "cache")
    return out, stats


def test_xml_build_does_not_prepend_bismillah_to_verse_text(built_from_xml):
    out, _ = built_from_xml
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.text_ar == "قُلْ هُوَ ٱللَّهُ أَحَدٌ"


def test_xml_build_stores_bismillah_separately(built_from_xml):
    out, _ = built_from_xml
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.bismillah == "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"


def test_xml_build_al_fatiha_1_1_has_no_bismillah_field(built_from_xml):
    out, _ = built_from_xml
    rec = db.get_record(db.connect(out), "quran:1:1")
    assert rec.text_ar.startswith("بِسْمِ")  # it IS the Bismillah here
    assert rec.bismillah is None


def test_xml_build_at_tawbah_has_no_bismillah_field(built_from_xml):
    out, _ = built_from_xml
    rec = db.get_record(db.connect(out), "quran:9:1")
    assert rec.bismillah is None


def test_xml_build_ordinary_verse_has_no_bismillah_field(built_from_xml):
    out, _ = built_from_xml
    rec = db.get_record(db.connect(out), "quran:112:2")
    assert rec.bismillah is None


# --- Regression: build_corpus's translation pass must dispatch on format --
#
# build_corpus's translation pass used to call parse_tanzil unconditionally,
# ignoring locked.format, even though fetch_source (and the Arabic pass)
# already dispatched correctly. An XML-format translation source would be
# hash-verified with parse_tanzil_xml and then handed to parse_tanzil to be
# loaded -- which raises TanzilParseError, since XML doesn't match the
# "surah|ayah|text" line shape. This fixture uses an XML-format translation
# source specifically to prove the translation pass now dispatches too.

_XML_TRANSLATION_URL = "https://example.invalid/xml-trans"
_XML_TRANSLATION_RAW = (
    '<?xml version="1.0" encoding="utf-8" ?>\n'
    "<!-- copyright -->\n"
    "<quran>"
    '<sura index="1" name="s">'
    '<aya index="1" text="In the name of Allah, the Beneficent, the Merciful." />'
    '<aya index="2" text="Praise be to Allah, Lord of the Worlds," />'
    "</sura>"
    '<sura index="112" name="s2">'
    '<aya index="1" text="Say: He is Allah, the One!" />'
    '<aya index="2" text="Allah, the eternally Besought of all!" />'
    "</sura>"
    "</quran>\n"
)


@pytest.fixture()
def built_with_xml_translation(tmp_path, monkeypatch):
    raw_ar = FIXTURE.read_text(encoding="utf-8")
    sha_ar = _payload_sha256(raw_ar)

    raw_en = _XML_TRANSLATION_RAW
    sha_en = _xml_payload_sha256(raw_en)

    lock = tmp_path / "corpus.lock.toml"
    lock.write_text(
        'lockfile_version = 1\n'
        '[[source]]\n'
        'id = "tanzil-uthmani-1.1"\nkind = "quran-arabic"\nformat = "txt-2"\n'
        'title = "Tanzil Uthmani"\npublisher = "Tanzil Project"\n'
        'edition = "1.1"\n'
        f'url = "{_ARABIC_URL}"\n'
        'license_id = "CC-BY-3.0"\nlicense_url = "https://tanzil.net/docs/text_license"\n'
        f'content_sha256 = "{sha_ar}"\nexpected_lines = 4\nmodifications = "none"\n'
        '\n'
        '[[source]]\n'
        'id = "some-xml-translation"\nkind = "quran-translation"\nformat = "xml"\n'
        'title = "Test XML Translation"\n'
        f'url = "{_XML_TRANSLATION_URL}"\n'
        'license_id = "public-domain"\n'
        f'content_sha256 = "{sha_en}"\nexpected_lines = 4\nmodifications = "none"\n',
        encoding="utf-8")

    raws = {_ARABIC_URL: raw_ar, _XML_TRANSLATION_URL: raw_en}
    monkeypatch.setattr("sanad_ingest.fetch._download", lambda url: raws[url])
    out = tmp_path / "sanad.db"
    stats = build_corpus(lock, out, tmp_path / "cache")
    return out, stats


def test_translation_pass_dispatches_on_xml_format(built_with_xml_translation):
    out, stats = built_with_xml_translation
    assert stats["translations"] == 4
    conn = db.connect(out)
    row = conn.execute(
        "SELECT text FROM translations WHERE record_id='quran:112:1' "
        "AND source_id='some-xml-translation'").fetchone()
    assert row["text"] == "Say: He is Allah, the One!"


# --- Bukhari: the matn is the scored text, the isnad is not ----------------
#
# These build the REAL corpus from the real lockfile, not a fixture lockfile.
# The brief sketched `build_corpus(db, only_sources=[...])`; no such parameter
# exists, and adding one would be production code shaped by test convenience
# (ruling R4). The build is done once per module instead, and every assertion
# below runs against the whole corpus -- which is also the only way the
# reference_display uniqueness check means anything, since a collision is by
# definition a property of the full set.

REAL_LOCKFILE = Path("ingest/corpus.lock.toml")
REAL_CACHE = Path(".corpus-cache")

# A narrator in hadith 1's chain ("al-Humaydi") and nowhere in any matn. Built
# from codepoints, not typed: an Arabic literal that renders identically can
# carry a different normalization and would make this test pass for the wrong
# reason -- or fail for one. See MEMORY: the character-in-transit defect.
_AL_HUMAYDI = "".join(chr(c) for c in (
    0x0627, 0x0644, 0x062D, 0x0645, 0x064A, 0x062F, 0x064A))       # الحميدي
# "haddathana" -- the narration verb that opens an isnad, never a matn.
_HADDATHANA = "".join(chr(c) for c in (
    0x062D, 0x062F, 0x062B, 0x0646, 0x0627))                        # حدثنا
# The mukarrar marker: a bare miim, as the edition prints it.
_MIIM = chr(0x0645)


@pytest.fixture(scope="module")
def real_corpus(tmp_path_factory):
    """The real corpus, built SOURCE-ONLY then materialised.

    `build_corpus` now emits a source-only DB (no norms, no record_variants, no
    records_fts); the derived data every assertion below reads is produced by
    materialize(). The build's own source-only shape is asserted by
    `test_build_output_is_source_only`; here we want the full corpus.
    """
    d = tmp_path_factory.mktemp("real-corpus")
    src = d / "corpus.db"
    report = d / "hadith-noise-report.md"
    stats = build_corpus(REAL_LOCKFILE, src, REAL_CACHE, noise_report=report)
    # Task 5 will replace this inline materialize with the shared session fixture.
    out = d / "materialized.db"
    materialize(str(src), str(out))
    return out, stats, report


def test_builds_hadith_records_with_matn_as_the_scored_text(real_corpus):
    out, _, _ = real_corpus
    conn = db.connect(out)
    n = conn.execute("SELECT count(*) FROM records WHERE kind='hadith'").fetchone()[0]
    assert n == 33949  # Task 15: +4341 Ibn Majah (7129 Bukhari + 7460 Muslim + 5274 Abu Dawud + 3976 Tirmidhi + 5769 Nasai)
    row = conn.execute(
        "SELECT text_ar, isnad_ar, norm_light, norm_standard, norm_aggressive "
        "FROM records WHERE id='hadith:bukhari:1'").fetchone()
    matn, isnad = row["text_ar"], row["isnad_ar"]
    assert isnad and len(isnad) > 100, "the chain must be stored"
    assert len(matn) < len(isnad), "hadith 1's matn is shorter than its chain"
    assert _HADDATHANA not in matn, "narration verbs belong to the isnad, not the matn"
    for col in ("norm_light", "norm_standard", "norm_aggressive"):
        assert row[col], f"{col} must be populated"
        assert _HADDATHANA not in row[col], f"{col} must derive from the matn alone"


def test_fts_does_not_index_the_isnad(real_corpus):
    """Searching a narrator from hadith 1's chain must not retrieve hadith 1.

    MEASURED, and not what was expected: al-Humaydi is NOT unique to hadith
    1's chain. He appears inside 11 other records' *matns*, because this
    edition appends supplementary chains after a narration ("زاد الحميدي
    حدثنا سفيان..." -- "al-Humaydi added: Sufyan narrated to us"), and the
    source marks only the FIRST isnad/matn boundary with "*". So "zero hits
    corpus-wide" is not a true property of this corpus and a test asserting
    it would be asserting a falsehood.

    The property that IS true, and is the one that matters, is that the term
    does not reach hadith 1 -- whose chain is the only place it occurs in
    that record. Paired with the exhaustive check below, this pins the
    isnad out of the index without overclaiming.
    """
    out, _, _ = real_corpus
    hits = {r[0] for r in db.connect(out).execute(
        "SELECT record_id FROM records_fts WHERE records_fts MATCH ?",
        (_AL_HUMAYDI,)).fetchall()}
    assert "hadith:bukhari:1" not in hits, "the isnad must not be searchable text"


def test_the_narrator_name_really_is_in_the_stored_chain(real_corpus):
    # Guards the test above from passing vacuously: if al-Humaydi were not in
    # hadith 1's chain at all, "hadith 1 not retrieved" would prove nothing.
    out, _, _ = real_corpus
    rec = db.get_record(db.connect(out), "hadith:bukhari:1")
    assert _AL_HUMAYDI in rec.isnad_ar
    assert _AL_HUMAYDI not in rec.text_ar


def test_fts_indexes_the_record_norms_and_nothing_else(real_corpus):
    # The exhaustive form of the test above, over every index row: the indexed
    # text must be byte-identical to the column it claims to index. Concatenating
    # anything extra -- an isnad, say -- shows up here even if no single narrator
    # term happens to prove it.
    #
    # Two clauses because there are two sources of an index row. The primary
    # rows must equal `records`; the variant rows must equal `record_variants`.
    # Checking only the first would let a variant row carry anything at all,
    # since it does not join to a `records` norm in the first place.
    out, _, _ = real_corpus
    conn = db.connect(out)
    differing = conn.execute(
        "SELECT count(*) FROM records_fts f JOIN records r ON r.id = f.record_id"
        " WHERE f.variant = 'primary'"
        "   AND (f.norm_standard IS NOT r.norm_standard"
        "     OR f.norm_aggressive IS NOT r.norm_aggressive)").fetchone()[0]
    assert differing == 0
    differing_variants = conn.execute(
        "SELECT count(*) FROM records_fts f JOIN record_variants v"
        "   ON v.record_id = f.record_id AND v.variant = f.variant"
        " WHERE f.variant <> 'primary'"
        "   AND (f.norm_standard IS NOT v.norm_standard"
        "     OR f.norm_aggressive IS NOT v.norm_aggressive)").fetchone()[0]
    assert differing_variants == 0
    # ... and no index row belongs to neither source.
    orphans = conn.execute(
        "SELECT count(*) FROM records_fts f WHERE f.variant <> 'primary'"
        " AND NOT EXISTS (SELECT 1 FROM record_variants v"
        "                 WHERE v.record_id = f.record_id"
        "                   AND v.variant = f.variant)").fetchone()[0]
    assert orphans == 0


def test_every_hadith_norm_derives_from_its_matn_alone(real_corpus):
    out, _, _ = real_corpus
    rows = db.connect(out).execute(
        "SELECT id, text_ar, norm_light, norm_standard, norm_aggressive"
        " FROM records WHERE kind='hadith'").fetchall()
    assert len(rows) == 33949  # Task 15: +4341 Ibn Majah
    for row in rows:
        for form in ("light", "standard", "aggressive"):
            assert row[f"norm_{form}"] == normalize(row["text_ar"], form), row["id"]


def test_corpus_holds_both_the_quran_and_the_hadith(real_corpus):
    out, _, _ = real_corpus
    counts = dict(db.connect(out).execute(
        "SELECT kind, count(*) FROM records GROUP BY kind").fetchall())
    assert counts == {"ayah": 6236, "hadith": 33949}  # Task 15: +4341 Ibn Majah


def test_hadith_records_carry_their_collection_metadata(real_corpus):
    out, _, _ = real_corpus
    rec = db.get_record(db.connect(out), "hadith:bukhari:1")
    assert rec.collection == "bukhari"
    assert rec.numbering_scheme == "bugha-1987"
    assert rec.hadith_no == "1"
    assert rec.book_no == 1
    assert rec.chapter_ar
    assert rec.surah is None and rec.ayah is None and rec.bismillah is None


def test_every_hadith_reference_display_is_unique(real_corpus):
    # Two records rendering the same citation while carrying different text is
    # the duplicate-verse problem Stage A solved once with `also_at`, back
    # again. Five printed numbers appear twice in Bukhari; Muslim has its own
    # collisions, handled the same way. Task 11 also checks that the two
    # collections' citations never collide with EACH OTHER -- "reference_display"
    # is prefixed with the collection's own printed name ("Sahih al-Bukhari" vs
    # "Sahih Muslim"), so two different editions numbering their narrations
    # identically is not, on its own, a collision. Task 12 (Abu Dawud, prefixed
    # "Sunan Abi Dawud"), Task 13 (Tirmidhi, prefixed "Jami at-Tirmidhi"),
    # Task 14 (Nasai, prefixed "Sunan an-Nasai"), and Task 15 (Ibn Majah,
    # prefixed "Sunan Ibn Majah") join the same check with the same result:
    # zero collisions, measured, not assumed to generalise from two
    # collections to six.
    out, _, _ = real_corpus
    rows = db.connect(out).execute(
        "SELECT reference_display FROM records WHERE kind='hadith'").fetchall()
    refs = [r[0] for r in rows]
    assert len(refs) == 33949
    assert len(set(refs)) == 33949


def test_mukarrar_variant_is_marked_in_the_citation(real_corpus):
    # 619 and "619 م" are different narrations: 27 degrees vs 25.
    out, _, _ = real_corpus
    conn = db.connect(out)
    assert db.get_record(conn, "hadith:bukhari:619").reference_display == \
        "Sahih al-Bukhari 619"
    assert db.get_record(conn, "hadith:bukhari:619-2").reference_display == \
        f"Sahih al-Bukhari 619 {_MIIM}"
    a = db.get_record(conn, "hadith:bukhari:619").text_ar
    b = db.get_record(conn, "hadith:bukhari:619-2").text_ar
    assert a != b, "the two 619s are different narrations, not a duplicate row"


def test_bare_collision_is_disambiguated_by_ordinal(real_corpus):
    # 3905 is printed twice with no marker at all.
    out, _, _ = real_corpus
    conn = db.connect(out)
    assert db.get_record(conn, "hadith:bukhari:3905").reference_display == \
        "Sahih al-Bukhari 3905"
    assert db.get_record(conn, "hadith:bukhari:3905-2").reference_display == \
        "Sahih al-Bukhari 3905 (2)"


def test_noise_report_lists_every_flagged_record(real_corpus):
    _, _, report = real_corpus
    text = report.read_text(encoding="utf-8")
    assert "no text was altered" in text.lower()
    assert "eval" in text.lower(), "the report must say why it exists"
    for record_id in ("hadith:bukhari:58", "hadith:bukhari:4236",
                      "hadith:bukhari:4449", "hadith:bukhari:5953",
                      "hadith:bukhari:6212", "hadith:bukhari:6965",
                      "hadith:bukhari:6966"):
        assert f"`{record_id}`" in text, f"{record_id} missing from the report"


def test_damage_that_moved_into_an_addendum_is_still_in_the_corpus(real_corpus):
    """3291, 6102 and 6967 were flagged before the secondary-narration fix
    and are not flagged now. That is correct and it is not a silent loss: their
    damaged characters were in the appended narration, which is no longer
    part of the scored, searched text the report exists to protect -- the
    same reason the isnad has never been scanned. The characters themselves
    are still there, unaltered, which is what this asserts. Nothing was
    cleaned up; the boundary moved.
    """
    out, _, report = real_corpus
    text = report.read_text(encoding="utf-8")
    conn = db.connect(out)
    for record_id, damaged in (("hadith:bukhari:3291", "5"),
                               ("hadith:bukhari:6102", "?"),
                               ("hadith:bukhari:6967", "%")):
        assert f"`{record_id}`" not in text
        rec = db.get_record(conn, record_id)
        assert damaged not in rec.text_ar
        assert damaged in rec.addenda_ar, record_id


def test_noise_report_is_a_review_artifact_not_a_filter(real_corpus):
    # Every flagged record is still in the corpus, unaltered.
    out, _, _ = real_corpus
    conn = db.connect(out)
    for record_id in ("hadith:bukhari:58", "hadith:bukhari:6966"):
        assert db.get_record(conn, record_id) is not None


def test_duplicate_reference_display_aborts_the_build():
    # The uniqueness rule is enforced in code, not only asserted about today's
    # edition. A future source (or a re-OCR) that produced two records behind
    # one citation must stop the build rather than ship an ambiguous corpus.
    from sanad_ingest.build import BuildError, _hadith_records
    from sanad_ingest.lockfile import LockedSource
    from sanad_ingest.openiti import HadithUnit, ParsedOpeniti

    def unit(record_id):
        return HadithUnit(hadith_no="7", record_id=record_id, is_repeat=True,
                          kitab_no=1, kitab_ar="k", bab_ar="b",
                          isnad_ar="i", matn_ar="m", addenda_ar=None)

    parsed = ParsedOpeniti(units=[unit("hadith:bukhari:7"), unit("hadith:bukhari:7-2")],
                           attribution="", content_sha256="0" * 64, noisy=[])
    locked = LockedSource(
        id="x", kind="hadith-arabic", format="openiti-markdown", title="X",
        url="https://example.invalid/x", license_id="public-domain",
        content_sha256="0" * 64, modifications="none", expected_records=2,
        collection="bukhari")
    with pytest.raises(BuildError, match="Sahih al-Bukhari 7"):
        _hadith_records(parsed, locked)


# --- Task 8: _reference_display is collection-aware -------------------------
#
# The title prefix ("Sahih al-Bukhari", "Sahih Muslim", ...) is the ONLY thing
# that changes with `collection`. is_repeat's mukarrar miim and the
# occurrence-counter suffix are unrelated to which collection a hadith belongs
# to and must keep working identically for every collection (ruling R-A3-10).

def _make_unit(hadith_no="1", is_repeat=False):
    from sanad_ingest.openiti import HadithUnit
    return HadithUnit(hadith_no=hadith_no, record_id=f"hadith:x:{hadith_no}",
                      is_repeat=is_repeat, kitab_no=1, kitab_ar="k", bab_ar="b",
                      isnad_ar="i", matn_ar="m", addenda_ar=None)


def test_reference_display_bukhari_is_unchanged():
    from sanad_ingest.build import _reference_display
    assert _reference_display("bukhari", _make_unit("1"), 1) == "Sahih al-Bukhari 1"


def test_reference_display_maps_each_collection_to_its_title():
    from sanad_ingest.build import _reference_display
    unit = _make_unit("1")
    expected = {
        "bukhari": "Sahih al-Bukhari 1",
        "muslim": "Sahih Muslim 1",
        "abudawud": "Sunan Abi Dawud 1",
        "tirmidhi": "Jami at-Tirmidhi 1",
        "nasai": "Sunan an-Nasai 1",
        "ibnmajah": "Sunan Ibn Majah 1",
    }
    for collection, want in expected.items():
        assert _reference_display(collection, unit, 1) == want


def test_reference_display_unknown_collection_raises():
    from sanad_ingest.build import BuildError, _reference_display
    with pytest.raises(BuildError):
        _reference_display("no-such-collection", _make_unit("1"), 1)


def test_reference_display_mukarrar_miim_for_non_bukhari_collection():
    from sanad_ingest.build import _reference_display
    unit = _make_unit("619", is_repeat=True)
    assert _reference_display("muslim", unit, 1) == f"Sahih Muslim 619 {_MIIM}"


def test_reference_display_occurrence_suffix_for_non_bukhari_collection():
    from sanad_ingest.build import _reference_display
    unit = _make_unit("3905", is_repeat=False)
    assert _reference_display("muslim", unit, 2) == "Sahih Muslim 3905 (2)"


# --- Task 8 fix round 1 (R-A3-12): collection threaded into the openiti
# parser, and the build guards the id<->collection invariant ----------------
#
# Task 8 wired `collection` into every downstream consumer of `LockedSource`
# (Record.collection, _reference_display, the audit-list lookups) but left
# `_parse`'s call to `parser_for(locked.format)(raw)` passing no `collection`
# at all -- so `parse_openiti` fell back to its own "bukhari" default and
# every non-Bukhari hadith source (Tasks 11-15) would have minted
# "hadith:bukhari:N" ids regardless of its real collection. This is the fix.

_MUSLIM_BAA = chr(0x0628)
_MUSLIM_HADDATHANA = "".join(
    chr(c) for c in (0x062D, 0x062F, 0x062B, 0x0646, 0x0627))  # حدثنا
_MUSLIM_AN = "".join(chr(c) for c in (0x0639, 0x0646))          # عن


def _openiti_snippet(number: str, matn: str) -> str:
    """A minimal openiti-markdown unit, same shape as
    tests/ingest/test_openiti.py's `_muslim_unit` fixture builder."""
    baa = _MUSLIM_BAA
    return (f"#META#Header#End#\n### | {baa * 5}\n"
            f"# {number} {_MUSLIM_HADDATHANA} {baa * 6} {_MUSLIM_AN} "
            f"{baa * 6} * {matn}\n")


def _muslim_locked(**overrides) -> LockedSource:
    kwargs = dict(
        id="test-muslim-source", kind="hadith-arabic", format="openiti-markdown",
        title="Test Muslim Source", url="https://example.invalid/muslim",
        license_id="public-domain", content_sha256="0" * 64,
        modifications="none", expected_records=1, collection="muslim")
    kwargs.update(overrides)
    return LockedSource(**kwargs)


def test_parse_threads_collection_into_the_openiti_parser():
    """`_parse` must not silently default a non-Bukhari source to Bukhari's
    "bukhari" collection: the resulting record ids must carry the source's
    OWN collection, not the parser's fallback."""
    from sanad_ingest.build import _parse
    matn = f"{_MUSLIM_BAA * 20} {_MUSLIM_BAA * 20}"
    raw = _openiti_snippet("1", matn)
    parsed = _parse(_muslim_locked(), raw)
    assert len(parsed.units) == 1
    assert parsed.units[0].record_id == "hadith:muslim:1"
    assert not parsed.units[0].record_id.startswith("hadith:bukhari:")


def test_hadith_records_rejects_a_record_id_that_does_not_match_the_collection():
    """The fail-loud guard: if a unit's id ever disagreed with its own
    source's `collection` (a wiring bug, not a data problem), the build must
    stop rather than silently cite the wrong collection."""
    from sanad_ingest.build import BuildError, _hadith_records
    from sanad_ingest.openiti import HadithUnit, ParsedOpeniti

    mismatched = HadithUnit(
        hadith_no="1", record_id="hadith:bukhari:1", is_repeat=False,
        kitab_no=1, kitab_ar="k", bab_ar="b", isnad_ar="i", matn_ar="m",
        addenda_ar=None)
    parsed = ParsedOpeniti(units=[mismatched], attribution="",
                           content_sha256="0" * 64, noisy=[])
    locked = _muslim_locked()
    with pytest.raises(BuildError, match="hadith:bukhari:1"):
        _hadith_records(parsed, locked)


# --- fix round 1: secondary narrations are stored, not scored --------------

def test_the_appended_narrations_are_stored_but_never_scored(real_corpus):
    """583 records carried an addendum after Task 12's first build: Bukhari's
    392 plus Muslim's 122 plus Abu Dawud's 69.

    Fix round 1 (R-A3-18) moves this to 1,376: the compiler-commentary split
    gives an addendum to most of the 806 Abu Dawud matns that carry Abu
    Dawud's own "qala Abu Dawud ..." remark (793 of them had none before at
    all), and the cut-override table corrects 11 more boundaries. Bukhari's
    392 and Muslim's 122 are untouched -- the split is scoped to
    `collection == "abudawud"` and proven so by the byte-identity check in
    the fix-round report.

    Fix round 2 (R-A3-22) moves this again, to 1,385: the marker's own two
    near-misses (4129, 5239, one via a widened fallback pattern and one via a
    second hand-audited cut-override boundary) plus 7 newly-split "qala Abu
    Ali" remarks in Abu Ali al-Lu'lu'i's own voice (911, 1096, 1391, 3220,
    3437, 4924, 5190) -- 9 more addendum-bearing records total, none of them
    Bukhari or Muslim.

    Fix round 3 (R-A3-23) moves this to 1,387: the marker only ever
    recognised the NOMINATIVE case of the compiler's kunya; two records
    (1234, 1854) quote him in the ACCUSATIVE ("sami'tu Aba Dawud yaqulu
    ..."), a case `_split_heard_commentary` now covers.

    Task 13 (Tirmidhi) moves this to 5,142: Tirmidhi's own compiler-commentary
    markers (his kunya-based verdicts, "wa fi al-bab", "hadha hadith ...",
    "wa fi al-hadith qissa[ tawila]", "wa hadha asahh") and its own
    `NEAR_MISS_CUT_OVERRIDE` entry each cut a trailing remark into an
    addendum the same way Abu Dawud's did -- see
    test_tirmidhi_record_count_and_scorability for the full account.

    Task 14 (Nasai) moves this to 5,574 across two fix rounds (+274, then
    +60/+2 Tirmidhi, then +96). Task 15 (Ibn Majah) moves it to 5,740: 166
    cut records, its own TWO editorial voices (al-Qattan's aside, the
    compiler's own) plus two hand-audited `NEAR_MISS_CUT_OVERRIDE` boundaries
    -- see test_ibnmajah_record_count_and_scorability for the full account.

    hadith 22 is one of the three boundaries named in the fix brief: the
    primary matn ends at "...as the seed grows beside a stream", and a second
    chain ("Wuhayb said: Amr narrated to us...") follows it with a variant
    wording. Before this fix the chain and the variant were both inside
    text_ar and both scored.

    "Never scored" means never scored AS PART OF text_ar. Since round 5 the
    rejoined text is scored as the record's second representation; see
    test_the_full_printed_text_is_scored_alongside_the_primary.
    """
    out, _, _ = real_corpus
    conn = db.connect(out)
    n = conn.execute(
        "SELECT count(*) FROM records WHERE addenda_ar IS NOT NULL").fetchone()[0]
    assert n == 5846  # Task 16 A1: +81 Bukhari, +25 Muslim compiler-commentary
    rec = db.get_record(conn, "hadith:bukhari:22")
    assert rec.addenda_ar and _HADDATHANA in rec.addenda_ar
    assert _HADDATHANA not in rec.text_ar
    assert rec.text_ar_sha256 == hashlib.sha256(
        rec.text_ar.encode("utf-8")).hexdigest()
    for form in ("light", "standard", "aggressive"):
        assert getattr(rec, f"norm_{form}") == normalize(rec.text_ar, form)
        assert _HADDATHANA not in getattr(rec, f"norm_{form}")


def test_no_addendum_reaches_the_primary_representation(real_corpus):
    """Exhaustive over all 1,376, in both the stored and the indexed text.

    The other half of the guarantee is
    test_fts_indexes_the_record_norms_and_nothing_else, which pins each index
    row to the column it claims to index. Together: the addendum is not in the
    primary's norms, and the primary index row is nothing but those norms.

    579, not 583, after Task 12's first build: four cut records also carried a
    primary-level unscorable verdict, so their PRIMARY had no index row --
    Bukhari's 237 (a "bayna" clause ending at the chain-transfer mark), Task
    11's Muslim 1915-3 and 546-3 (both editorial pointers: "the chain, and in
    his version" / "with this chain"), and Task 12's Abu Dawud 2225 (Abu
    Dawud's own numbered remark about how other narrators transmitted an
    isnad/wording differently -- `_EDITORIAL_DISCUSSION`).

    1,335, not 1,376, after fix round 1 (R-A3-18): 41 cut records now carry a
    primary-level unscorable verdict -- the same 4 plus 37 more. 36 are fix
    round 1's own new `UNSCORABLE["abudawud"]` entries, every one excluded
    BECAUSE the compiler-commentary split gave its short post-split primary
    an addendum in the first place; the 37th is hadith:abudawud:2331
    (`_LEXICAL_GLOSS`, already on the list before this round), which gained
    an addendum the same way. The two counts are asserted separately rather
    than relaxed into one, so that a record silently falling out of the index
    cannot hide inside this total.

    1,344, not 1,335, after fix round 2 (R-A3-22): the unscorable-with-
    addendum count itself is unchanged at 41 -- none of the 9 newly
    addendum-bearing records (see the test above) is also unscorable, so
    every one of them adds a row here. Confirmed directly, not by arithmetic
    alone: `41` was re-measured against the round-2 DB before this docstring
    was written.

    1,346, not 1,344, after fix round 3 (R-A3-23): 41 unchanged again --
    1234 and 1854 are both genuine, complete, scorable matns -- so both new
    addendum-bearing records add a row here.

    105 unscorable-with-addendum and 5,037 scorable-with-addendum after Task
    13 (Tirmidhi): 64 of Tirmidhi's cut records are also on its own audit
    list (`test_every_other_excluded_record_is_excluded_whole`), so the
    unscorable-with-addendum count rises by exactly 64 (41 + 64 = 105); the
    remaining 3,691 new Tirmidhi cut records are scorable, so the
    scorable-with-addendum count rises by 3,691 (1,346 + 3,691 = 5,037).

    122 unscorable-with-addendum (unchanged) and 5,618 scorable-with-addendum
    after Task 15 (Ibn Majah): none of its 166 cut records is also on
    `UNSCORABLE["ibnmajah"]` -- hadith:ibnmajah:413, that list's one entry,
    was never cut, it is a bare pointer excluded whole -- so all 166 add to
    the scorable-with-addendum count instead (5,452 + 166 = 5,618).

    Task 16: A1's Bukhari+Muslim commentary split makes these 127 / 5,719 (+5
    unscorable-with-addendum from the split-exposed Muslim pointers, +101
    net scorable-with-addendum). A2's pointer/deferral sweep then moves
    muslim:1669-6 from scorable to unscorable, so its addendum crosses over:
    128 unscorable-with-addendum and 5,718 scorable-with-addendum.

    Task 16 A2 fix-round (back-reference/omission shapes) moves these to
    136 / 5,710: 8 of the 151 newly-excluded records (muslim:1433-7 and
    tirmidhi 328/493/888/985/1389/1452/2824-2) already carried an addendum a
    prior round had cut, so each crosses from scorable-with-addendum to
    unscorable-with-addendum. The other 143 have no addendum, so neither count
    sees them.
    """
    out, _, _ = real_corpus
    conn = db.connect(out)
    assert conn.execute(
        "SELECT count(*) FROM records WHERE addenda_ar IS NOT NULL"
        " AND unscorable_reason IS NOT NULL").fetchone()[0] == 136  # A2 fix-round +8
    rows = conn.execute(
        "SELECT r.id, r.text_ar, r.addenda_ar, f.norm_standard,"
        "       f.norm_aggressive FROM records r"
        " JOIN records_fts f ON f.record_id = r.id AND f.variant = 'primary'"
        " WHERE r.addenda_ar IS NOT NULL").fetchall()
    assert len(rows) == 5710  # A2 fix-round: -8 (newly-unscorable records that carried an addendum)
    for row in rows:
        assert row["addenda_ar"] not in row["text_ar"], row["id"]
        for form in ("standard", "aggressive"):
            assert normalize(row["addenda_ar"], form) not in row[f"norm_{form}"], \
                row["id"]


def test_the_full_printed_text_is_scored_alongside_the_primary(real_corpus):
    """Every cut record has a second, scorable representation, and it is the
    edition's own text: `text_ar + " " + addenda_ar`, byte for byte, with
    every norm derived from that exact string.

    This is what makes the cut's precision non-load-bearing. Before it, an
    over-cut (342 and 3164, the Isra'/Mi'raj, split in the middle of one
    continuous narration) put ~700 characters of Sahih al-Bukhari out of
    reach of every tier.

    5,142 after Task 13 (Tirmidhi): every one of its 3,755 cut records gets
    the same second representation, no exceptions.

    5,740 after Task 15 (Ibn Majah): its 166 cut records get the same second
    representation too, no exceptions (5,574 + 166 = 5,740).
    """
    out, _, _ = real_corpus
    conn = db.connect(out)
    rows = conn.execute(
        "SELECT r.id, r.text_ar, r.addenda_ar, r.unscorable_reason,"
        "       v.variant, v.text_ar AS whole, v.norm_light, v.norm_standard,"
        "       v.norm_aggressive FROM records r"
        " LEFT JOIN record_variants v ON v.record_id = r.id"
        " WHERE r.addenda_ar IS NOT NULL").fetchall()
    assert len(rows) == 5846  # Task 16 A1: +81 Bukhari, +25 Muslim
    checked = 0
    for row in rows:
        # 237 (and Task 11's Muslim 1915-3, 546-3, and fix round 1's 41
        # unscorable-with-addendum Abu Dawud records) are here too. Their
        # `unscorable_reason` is a judgement about their primary matn and
        # carries no verdict on the text printed behind them.
        assert row["variant"] == "full", row["id"]
        assert row["whole"] == row["text_ar"] + " " + row["addenda_ar"], row["id"]
        for form in ("light", "standard", "aggressive"):
            assert row[f"norm_{form}"] == normalize(row["whole"], form), row["id"]
        checked += 1
    assert checked == 5846  # Task 16 A1: +81 Bukhari, +25 Muslim


def test_a_record_with_no_addendum_has_no_second_representation(real_corpus):
    """Nothing is indexed twice for no reason: the full text of an uncut
    record IS its primary, and a duplicate row would let one record occupy two
    places in a tie set."""
    out, _, _ = real_corpus
    n = db.connect(out).execute(
        "SELECT count(*) FROM record_variants v JOIN records r ON r.id = v.record_id"
        " WHERE r.addenda_ar IS NULL").fetchone()[0]
    assert n == 0


def test_an_unscorable_records_full_text_is_still_a_representation(real_corpus):
    """237 carries an addendum and is on the unscorable audit list, and the
    two facts are about different strings.

    Its primary is `bayna rasul allah ... ha`, a subordinate clause ending at
    the chain-transfer mark -- rightly unscorable. Its addendum is 869
    characters, the longest in this edition, and holds the complete narration
    of the camel entrails placed on the Prophet's back at the Ka'ba. The rule
    that excluded both applied a judgement made about 40 characters to 869 it
    had never seen, and a reader quoting Bukhari 237 as the edition prints it
    was told it was not in this corpus.

    So: no primary index row, one full-text index row, one variant.
    """
    out, _, _ = real_corpus
    conn = db.connect(out)
    rec = db.get_record(conn, "hadith:bukhari:237")
    assert rec.addenda_ar and rec.unscorable_reason
    assert len(rec.addenda_ar) == 869
    assert conn.execute(
        "SELECT count(*) FROM record_variants WHERE record_id = 'hadith:bukhari:237'"
    ).fetchone()[0] == 1
    variants = [r[0] for r in conn.execute(
        "SELECT variant FROM records_fts WHERE record_id = 'hadith:bukhari:237'")]
    assert variants == ["full"]


def test_no_hadith_record_ships_an_empty_scored_text(real_corpus):
    """The bar is zero. Six records had one before this fix."""
    out, _, _ = real_corpus
    empty = [r[0] for r in db.connect(out).execute(
        "SELECT id FROM records WHERE kind='hadith'"
        " AND trim(text_ar) = ''").fetchall()]
    assert empty == []


def test_an_empty_scored_text_aborts_the_build():
    """Enforced in code, not only asserted about today's edition.

    A re-OCR that dropped a matn must stop the build. Silently excluding the
    record instead would lose a citable hadith with nobody noticing, which is
    this repo's most expensive recurring failure.
    """
    from sanad_ingest.build import BuildError, _hadith_records
    from sanad_ingest.lockfile import LockedSource
    from sanad_ingest.openiti import HadithUnit, ParsedOpeniti

    unit = HadithUnit(hadith_no="7", record_id="hadith:bukhari:7", is_repeat=False,
                      kitab_no=1, kitab_ar="k", bab_ar="b",
                      isnad_ar="i", matn_ar="   ", addenda_ar=None)
    parsed = ParsedOpeniti(units=[unit], attribution="", content_sha256="0" * 64,
                           noisy=[])
    locked = LockedSource(
        id="x", kind="hadith-arabic", format="openiti-markdown", title="X",
        url="https://example.invalid/x", license_id="public-domain",
        content_sha256="0" * 64, modifications="none", expected_records=1,
        collection="bukhari")
    with pytest.raises(BuildError, match="empty scored text"):
        _hadith_records(parsed, locked)


# --- fix round 3: editorial pointers are kept, displayed, never scored -----

# The audited list, restated here independently of the parser's copy. If the
# two ever disagree, one of them was edited without the audit being redone.
_UNSCORABLE_IDS = frozenset(f"hadith:bukhari:{n}" for n in (
    "127", "237", "335", "394", "549", "557", "587", "1379", "1915", "2483",
    "3457", "3750", "3777", "3801", "3957", "4540", "5454", "5837",
))  # Task 16 A2 added 587 (the "مثله إلى قوله" partial-quote deferral)
# Famous short matns, read in the source and ruled genuine: "war is deceit",
# "the moon split", "a rich man's delay is oppression", "every kindness is
# charity". They are the guard against a length heuristic creeping back in.
_GENUINE_SHORT_IDS = tuple(f"hadith:bukhari:{n}" for n in
                           ("2866", "3658", "2270", "5675"))


def test_editorial_pointers_are_kept_but_never_scored(real_corpus):
    """Bukhari's 17 are restated and checked as an exact set, unchanged since
    round 3. Task 11's Muslim audit list adds 721 more records across 235
    distinct texts (audit_lists.py's UNSCORABLE["muslim"]) -- too many to
    restate independently here without defeating the point of an
    independently-typed check, so Muslim is verified by count instead: the
    total flagged set must be exactly Bukhari's 17 plus Muslim's 721 plus
    Abu Dawud's 139, with no unaccounted-for record on any side.

    Abu Dawud's count was 103 after Task 12's first build. Fix round 1
    (R-A3-18) adds 36: once the compiler-commentary split cuts Abu Dawud's own
    "qala Abu Dawud ..." remarks away, 36 of the resulting post-split
    primaries turn out to be editorial apparatus themselves (pointer,
    deferral, one editorial remark about a wording variant, two wholly-Qur'anic
    qira'a reports) by the SAME 30-characters-or-fewer, read-in-context
    methodology the original 103 were found by -- see audit_lists.py's
    "abudawud" section, the block added for fix round 1.

    Task 13 (Tirmidhi) adds its own 80, by the same methodology: see
    `test_tirmidhi_record_count_and_scorability` for how that count was
    reached, including the one entry (2929) the by-hand audit missed and the
    materialize-time wholly-Qur'anic gate caught.

    Task 14 (Nasai) adds 53. Fix round 1 (R-A3-25) adds 2 more (1738, 3492).
    Fix round 2 (R-A3-27) adds 2 more still (207-2, 353, `_CHAIN_LEAK`): see
    `test_nasai_record_count_and_scorability`'s fix-round note for why.

    Task 15 (Ibn Majah) adds its own 1: hadith:ibnmajah:413
    (`UNSCORABLE["ibnmajah"]`), a bare "نحوه" pointer -- see
    `test_ibnmajah_bare_pointer_is_unscorable`.

    Task 16 A1 adds 5 Muslim (split-exposed pointer/deferral heads), then A2's
    non-length-capped sweep adds 1 more Bukhari (587) and 24 more Muslim
    (partial-quote deferrals), so Bukhari is now 18 and Muslim 750.

    Task 16 A2 fix-round (back-reference and omission shapes) adds 132 more
    Muslim, 6 more Abu Dawud and 13 more Tirmidhi -- back-references,
    meta-comments, omission notes and isnad-scaffold heads that deliver no
    narration of their own -- so Muslim is now 882, Abu Dawud 145 and Tirmidhi
    93. Bukhari (18), Nasai (57) and Ibn Majah (1) are unchanged: the same
    six-collection sweep found none of this class in them.

    Task 16 pre-Part-B cleanup, C0 (A2-residue) adds 5 more Muslim: four pure
    "bimana hadith X 'an Y" singletons that slipped the A2 fix-round's
    duplicate-string grouping (each is a unique string, so it never grouped
    with a sibling occurrence) -- the same class as the 19 "bimana hadith"
    entries the fix round already caught -- plus muslim:1704-2, adjudicated in
    context: a back-reference carrying only a narrator's-doubt remark about a
    transmitted numeral, no narrative content of its own. Muslim is now 887.
    """
    out, _, _ = real_corpus
    conn = db.connect(out)
    flagged = {r[0] for r in conn.execute(
        "SELECT id FROM records WHERE unscorable_reason IS NOT NULL").fetchall()}
    flagged_bukhari = {r for r in flagged if r.startswith("hadith:bukhari:")}
    flagged_muslim = {r for r in flagged if r.startswith("hadith:muslim:")}
    flagged_abudawud = {r for r in flagged if r.startswith("hadith:abudawud:")}
    flagged_tirmidhi = {r for r in flagged if r.startswith("hadith:tirmidhi:")}
    flagged_nasai = {r for r in flagged if r.startswith("hadith:nasai:")}
    flagged_ibnmajah = {r for r in flagged if r.startswith("hadith:ibnmajah:")}
    assert flagged_bukhari == set(_UNSCORABLE_IDS)
    assert len(flagged_muslim) == 887  # A2 fix-round +132, C0 residue +5
    assert len(flagged_abudawud) == 145  # A2 fix-round +6
    assert len(flagged_tirmidhi) == 93  # A2 fix-round +13
    assert len(flagged_nasai) == 57
    assert flagged_ibnmajah == {"hadith:ibnmajah:413"}
    assert flagged == (flagged_bukhari | flagged_muslim | flagged_abudawud
                        | flagged_tirmidhi | flagged_nasai | flagged_ibnmajah)
    for record_id in sorted(_UNSCORABLE_IDS):
        rec = db.get_record(conn, record_id)
        # Nothing is deleted: the record stays, keeps its citation, and keeps
        # the edition's words. Only its scorability changes.
        assert rec is not None, record_id
        assert rec.text_ar.strip(), record_id
        assert rec.reference_display.startswith("Sahih al-Bukhari "), record_id
        assert rec.unscorable_reason, record_id


def test_no_unscorable_primary_is_in_the_search_index(real_corpus):
    """All excluded primaries are out of the index. After Task 12's first
    build, only four had any index row at all -- their full printed text,
    which is a narration, not the apparatus the audit ruled on: Bukhari's
    237, Task 11's Muslim 1915-3 and 546-3 (both cut records whose primary is
    a pointer but whose addendum is a genuine narration), and Abu Dawud 2225
    (Abu Dawud's own editorial discussion of isnad variants, likewise cut
    with a genuine addendum behind the excluded primary).

    Fix round 1 (R-A3-18) raises this to 41: hadith:abudawud:2331 (already
    `_LEXICAL_GLOSS`) gains an addendum the compiler-commentary split cuts
    away from it, and every one of the round's 36 new
    `UNSCORABLE["abudawud"]` entries was excluded BECAUSE that same split gave
    its short post-split primary an addendum in the first place -- so all 36
    carry their compiler commentary as a genuine, scorable "full" representation.

    Task 13 (Tirmidhi) raises this to 105: the same pattern repeats for 64 of
    Tirmidhi's own `UNSCORABLE["tirmidhi"]` entries (its compiler-commentary
    split gave each a genuine, scorable full-text representation), listed
    here in ascending string order (Python's default, so e.g. "111" sorts
    before "1194" and both sort before "30" -- not numeric order).

    Task 14 (Nasai) raises this to 111 (the kunya marker's 6: 648, 1786,
    4588, 5123, 5194, 5695). Fix round 1 (R-A3-25) raises this to 120: the
    comparative-isnad family extension gives 7 more already-excluded Nasai
    records their own addendum for the first time (2232, 2295, 2412, 3492,
    4098, 4360, 4787), and the `_split_compiler_commentary` empty-head fix
    lets Tirmidhi's 46 and 566 correctly cut for the first time too (see
    `test_tirmidhi_record_count_and_scorability`'s fix-round note).

    Fix round 2 (R-A3-27) raises this to 122: 207-2 and 353 move to
    `UNSCORABLE["nasai"]`'s `_CHAIN_LEAK` group (the new "لم يذكر" arm cuts
    a trailing "and he did not mention <name>" remark off each, leaving zero
    genuine narrative content ahead of it), and both retain that remark as a
    scorable "full" addendum.

    Task 16 A1 raises this to 127 (the 5 split-exposed Muslim pointers each
    keep their addendum as a scorable "full" representation), then A2 raises it
    to 128: muslim:1669-6, moved to UNSCORABLE by the pointer/deferral sweep,
    keeps its A1 addendum as a "full" representation the same way -- listed in
    ascending string order below.

    Task 16 A2 fix-round raises this to 136: 8 of the 151 back-reference/
    omission records the sweep newly excluded already carried an addendum a
    prior round had cut, which stays as a scorable "full" representation
    (muslim:1433-7 and tirmidhi 328/493/888/985/1389/1452/2824-2). The other
    143 have no addendum and so add no index row. Listed in ascending string
    order below.
    """
    out, _, _ = real_corpus
    rows = db.connect(out).execute(
        "SELECT f.record_id, f.variant FROM records_fts f"
        " JOIN records r ON r.id = f.record_id"
        " WHERE r.unscorable_reason IS NOT NULL"
        " ORDER BY f.record_id").fetchall()
    assert [(r["record_id"], r["variant"]) for r in rows] == \
        [("hadith:abudawud:1200", "full"),
         ("hadith:abudawud:1302", "full"),
         ("hadith:abudawud:1405", "full"),
         ("hadith:abudawud:1604", "full"),
         ("hadith:abudawud:1636", "full"),
         ("hadith:abudawud:180", "full"),
         ("hadith:abudawud:1948", "full"),
         ("hadith:abudawud:2084", "full"),
         ("hadith:abudawud:209", "full"),
         ("hadith:abudawud:2097", "full"),
         ("hadith:abudawud:2225", "full"),
         ("hadith:abudawud:2331", "full"),
         ("hadith:abudawud:2397", "full"),
         ("hadith:abudawud:2468", "full"),
         ("hadith:abudawud:2580", "full"),
         ("hadith:abudawud:2585", "full"),
         ("hadith:abudawud:263", "full"),
         ("hadith:abudawud:300", "full"),
         ("hadith:abudawud:308", "full"),
         ("hadith:abudawud:3099", "full"),
         ("hadith:abudawud:3100", "full"),
         ("hadith:abudawud:3162", "full"),
         ("hadith:abudawud:3226", "full"),
         ("hadith:abudawud:3291", "full"),
         ("hadith:abudawud:3434", "full"),
         ("hadith:abudawud:3552", "full"),
         ("hadith:abudawud:3604", "full"),
         ("hadith:abudawud:3952", "full"),
         ("hadith:abudawud:3980", "full"),
         ("hadith:abudawud:3997", "full"),
         ("hadith:abudawud:4013", "full"),
         ("hadith:abudawud:4022", "full"),
         ("hadith:abudawud:4118", "full"),
         ("hadith:abudawud:4287", "full"),
         ("hadith:abudawud:4571", "full"),
         ("hadith:abudawud:4897", "full"),
         ("hadith:abudawud:533", "full"),
         ("hadith:abudawud:960", "full"),
         ("hadith:bukhari:237", "full"),
         ("hadith:muslim:1159-7", "full"),
         ("hadith:muslim:1238-2", "full"),
         ("hadith:muslim:1433-7", "full"),
         ("hadith:muslim:1532-2", "full"),
         ("hadith:muslim:1647-2", "full"),
         ("hadith:muslim:1669-6", "full"),
         ("hadith:muslim:1855-3", "full"),
         ("hadith:muslim:1915-3", "full"),
         ("hadith:muslim:546-3", "full"),
         ("hadith:nasai:1786", "full"),
         ("hadith:nasai:207-2", "full"),
         ("hadith:nasai:2232", "full"),
         ("hadith:nasai:2295", "full"),
         ("hadith:nasai:2412", "full"),
         ("hadith:nasai:3492", "full"),
         ("hadith:nasai:353", "full"),
         ("hadith:nasai:4098", "full"),
         ("hadith:nasai:4360", "full"),
         ("hadith:nasai:4588", "full"),
         ("hadith:nasai:4787", "full"),
         ("hadith:nasai:5123", "full"),
         ("hadith:nasai:5194", "full"),
         ("hadith:nasai:5695", "full"),
         ("hadith:nasai:648", "full"),
         ("hadith:tirmidhi:1051", "full"),
         ("hadith:tirmidhi:1104", "full"),
         ("hadith:tirmidhi:111", "full"),
         ("hadith:tirmidhi:119", "full"),
         ("hadith:tirmidhi:127", "full"),
         ("hadith:tirmidhi:1328", "full"),
         ("hadith:tirmidhi:1389", "full"),
         ("hadith:tirmidhi:1452", "full"),
         ("hadith:tirmidhi:148", "full"),
         ("hadith:tirmidhi:1605", "full"),
         ("hadith:tirmidhi:163", "full"),
         ("hadith:tirmidhi:166", "full"),
         ("hadith:tirmidhi:1662", "full"),
         ("hadith:tirmidhi:1697", "full"),
         ("hadith:tirmidhi:1904-2", "full"),
         ("hadith:tirmidhi:196", "full"),
         ("hadith:tirmidhi:2282", "full"),
         ("hadith:tirmidhi:2286", "full"),
         ("hadith:tirmidhi:2296", "full"),
         ("hadith:tirmidhi:2534", "full"),
         ("hadith:tirmidhi:2534-2", "full"),
         ("hadith:tirmidhi:2543-2", "full"),
         ("hadith:tirmidhi:256", "full"),
         ("hadith:tirmidhi:2568-2", "full"),
         ("hadith:tirmidhi:2570", "full"),
         ("hadith:tirmidhi:280", "full"),
         ("hadith:tirmidhi:2824-2", "full"),
         ("hadith:tirmidhi:285", "full"),
         ("hadith:tirmidhi:2864", "full"),
         ("hadith:tirmidhi:2929", "full"),
         ("hadith:tirmidhi:2934", "full"),
         ("hadith:tirmidhi:299", "full"),
         ("hadith:tirmidhi:30", "full"),
         ("hadith:tirmidhi:328", "full"),
         ("hadith:tirmidhi:343", "full"),
         ("hadith:tirmidhi:3435-2", "full"),
         ("hadith:tirmidhi:347", "full"),
         ("hadith:tirmidhi:349", "full"),
         ("hadith:tirmidhi:434", "full"),
         ("hadith:tirmidhi:441", "full"),
         ("hadith:tirmidhi:444", "full"),
         ("hadith:tirmidhi:46", "full"),
         ("hadith:tirmidhi:493", "full"),
         ("hadith:tirmidhi:504", "full"),
         ("hadith:tirmidhi:529", "full"),
         ("hadith:tirmidhi:535", "full"),
         ("hadith:tirmidhi:540", "full"),
         ("hadith:tirmidhi:559", "full"),
         ("hadith:tirmidhi:566", "full"),
         ("hadith:tirmidhi:569", "full"),
         ("hadith:tirmidhi:574", "full"),
         ("hadith:tirmidhi:599", "full"),
         ("hadith:tirmidhi:612", "full"),
         ("hadith:tirmidhi:627", "full"),
         ("hadith:tirmidhi:634", "full"),
         ("hadith:tirmidhi:636", "full"),
         ("hadith:tirmidhi:648", "full"),
         ("hadith:tirmidhi:654", "full"),
         ("hadith:tirmidhi:701", "full"),
         ("hadith:tirmidhi:704", "full"),
         ("hadith:tirmidhi:709", "full"),
         ("hadith:tirmidhi:717", "full"),
         ("hadith:tirmidhi:722", "full"),
         ("hadith:tirmidhi:786", "full"),
         ("hadith:tirmidhi:800", "full"),
         ("hadith:tirmidhi:836", "full"),
         ("hadith:tirmidhi:872", "full"),
         ("hadith:tirmidhi:888", "full"),
         ("hadith:tirmidhi:915", "full"),
         ("hadith:tirmidhi:926", "full"),
         ("hadith:tirmidhi:968", "full"),
         ("hadith:tirmidhi:971", "full"),
         ("hadith:tirmidhi:985", "full")]


def test_a_famous_short_matn_is_still_indexed_and_scorable(real_corpus):
    """The guard against over-reach, at the corpus level.

    Length is not the rule: these are 10 to 13 characters, shorter than three
    of the excluded records, and they are in the index.
    """
    out, _, _ = real_corpus
    conn = db.connect(out)
    for record_id in _GENUINE_SHORT_IDS:
        assert db.get_record(conn, record_id).unscorable_reason is None, record_id
        assert conn.execute(
            "SELECT count(*) FROM records_fts WHERE record_id = ? AND variant = 'primary'",
            (record_id,)).fetchone()[0] == 1, record_id


def test_nothing_outside_the_audited_hadith_is_unscorable(real_corpus):
    """Surah Ta-Ha's first ayah is two characters. The Qur'an side is untouched.

    The kind literal is checked against a count, not assumed: Qur'anic records
    are stored with kind 'ayah', and the first version of this test asked for
    kind='quran' -- a query that returns zero rows whatever the flag does, and
    would have passed while proving nothing.
    """
    out, _, _ = real_corpus
    conn = db.connect(out)
    assert conn.execute(
        "SELECT count(*) FROM records WHERE kind='ayah'").fetchone()[0] == 6236
    kinds = {r[0] for r in conn.execute(
        "SELECT DISTINCT kind FROM records"
        " WHERE unscorable_reason IS NOT NULL").fetchall()}
    assert kinds == {"hadith"}
    assert db.get_record(conn, "quran:20:1").unscorable_reason is None


def test_a_missing_audited_record_aborts_the_build():
    """An entry on the unscorable list must still name a record that exists.

    Without this, a future edition that dropped hadith 1379 would leave a
    silently unused entry behind -- the list would still look like it covered
    the corpus while covering one record less, and nothing would say so. The
    same failure direction as every other check here: stop, do not ship.
    """
    from sanad_ingest.build import BuildError, _hadith_records
    from sanad_ingest.lockfile import LockedSource
    from sanad_ingest.openiti import HadithUnit, ParsedOpeniti

    unit = HadithUnit(hadith_no="7", record_id="hadith:bukhari:7", is_repeat=False,
                      kitab_no=1, kitab_ar="k", bab_ar="b",
                      isnad_ar="i", matn_ar="m", addenda_ar=None)
    parsed = ParsedOpeniti(units=[unit], attribution="", content_sha256="0" * 64,
                           noisy=[])
    locked = LockedSource(
        id="x", kind="hadith-arabic", format="openiti-markdown", title="X",
        url="https://example.invalid/x", license_id="public-domain",
        content_sha256="0" * 64, modifications="none", expected_records=1,
        collection="bukhari")
    with pytest.raises(BuildError, match="hadith:bukhari:1379"):
        _hadith_records(parsed, locked)


def test_a_missing_do_not_cut_record_aborts_the_build():
    """The same check, for the other audited list -- and separately reachable.

    The unscorable list and the do-not-cut list are two different judgements
    about two different sets of records, and the loop over them is the only
    thing making the second one checked at all. With every unscorable record
    present and one do-not-cut record gone, the build must still stop: an
    entry that names a record the corpus no longer has is an audit quietly
    covering less than it claims, whichever list it sits on.
    """
    from sanad_ingest.audit_lists import NEVER_CUT, UNSCORABLE
    from sanad_ingest.build import BuildError, _hadith_records
    from sanad_ingest.lockfile import LockedSource
    from sanad_ingest.openiti import HadithUnit, ParsedOpeniti

    def _unit(record_id: str) -> HadithUnit:
        no = record_id.rsplit(":", 1)[1]
        return HadithUnit(hadith_no=no, record_id=record_id, is_repeat=False,
                          kitab_no=1, kitab_ar="k", bab_ar="b",
                          isnad_ar="i", matn_ar="m", addenda_ar=None)

    # everything on both lists except hadith 632, which this corpus has lost
    ids = sorted(set(UNSCORABLE["bukhari"]) |
                (set(NEVER_CUT["bukhari"]) - {"hadith:bukhari:632"}))
    assert "hadith:bukhari:6136" in ids, "only 632 may be missing"
    parsed = ParsedOpeniti(units=[_unit(i) for i in ids], attribution="",
                           content_sha256="0" * 64, noisy=[])
    locked = LockedSource(
        id="x", kind="hadith-arabic", format="openiti-markdown", title="X",
        url="https://example.invalid/x", license_id="public-domain",
        content_sha256="0" * 64, modifications="none", expected_records=len(ids),
        collection="bukhari")
    with pytest.raises(BuildError, match="hadith:bukhari:632"):
        _hadith_records(parsed, locked)

# --- C1: a hadith representation may not be wholly Qur'anic -----------------
#
# The wholly-Qur'anic guard moved to `sanad_ingest.materialize` in Stage A3
# Task 4 (it reads norm_standard, which the source-only build no longer
# computes). The rule itself -- token boundaries, one surah at a time,
# primaries and variants alike -- is unit-tested against the materialize
# function in tests/ingest/test_materialize.py. What stays HERE is the wiring:
# proof that the pipeline actually invokes the gate, so a deleted call is a
# failing test rather than a silent mutant.


def _source_hadith(text, *, record_id="hadith:bukhari:99999"):
    """A SOURCE-ONLY hadith Record: derived columns left NULL, like build emits."""
    from sanad.corpus.models import Record
    return Record(id=record_id, source_id="s", kind="hadith", collection="bukhari",
                  hadith_no="99999", numbering_scheme="bugha-1987", text_ar=text,
                  text_ar_sha256=None, norm_light=None, norm_standard=None,
                  norm_aggressive=None, reference_display=f"Sahih al-Bukhari {record_id}")


def test_materialize_runs_the_quranic_guard(tmp_path, monkeypatch, real_corpus):
    """The wiring, not the rule.

    Every unit test of the guard calls `_reject_wholly_quranic_representations`
    directly, so all of them would still pass if the call were deleted from
    `materialize()` -- a surviving mutant. An invariant nothing invokes is
    decoration.

    The poison is a real ayah, read out of the already-built corpus, so no
    Arabic is typed here and the two sides of the comparison are the same bytes
    by construction. It is appended AFTER `_hadith_records` returns, which makes
    this a test of the pipeline wiring rather than of the audit checks inside
    that function. The build now emits source-only, so the poison passes the
    build silently and it is materialize() that must halt on it.
    """
    from sanad_ingest import build as build_mod

    real_out, _, _ = real_corpus  # materialised; the ayat are present
    ayah = db.connect(real_out).execute(
        "SELECT text_ar FROM records WHERE id = 'quran:53:9'").fetchone()["text_ar"]
    assert ayah, "the poison has to be real scripture or this proves nothing"

    unpoisoned = build_mod._hadith_records

    def poisoned(parsed, locked):
        records = unpoisoned(parsed, locked)
        return [*records, _source_hadith(ayah, record_id="hadith:bukhari:99999")]

    monkeypatch.setattr(build_mod, "_hadith_records", poisoned)
    src = tmp_path / "poisoned-src.db"
    # The source-only build accepts the poison: it computes no norms to compare.
    build_corpus(REAL_LOCKFILE, src, REAL_CACHE)
    with pytest.raises(MaterializeError, match="wholly a quotation of the Qur'an"):
        materialize(str(src), str(tmp_path / "poisoned.db"))
