import hashlib
import re
from pathlib import Path

import pytest
from sanad.arabic.normalize import normalize
from sanad.corpus import db
from sanad_ingest.build import build_corpus

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


def test_normalized_columns_are_populated(built):
    out, _ = built
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.norm_standard == "قل هو الله احد"
    assert rec.norm_light != rec.norm_standard


def test_text_checksum_is_of_canonical_text(built):
    out, _ = built
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.text_ar_sha256 == hashlib.sha256(rec.text_ar.encode("utf-8")).hexdigest()


def test_attribution_block_is_stored_verbatim(built):
    out, _ = built
    row = db.connect(out).execute(
        "SELECT attribution FROM sources WHERE id='tanzil-uthmani-1.1'").fetchone()
    assert "PLEASE DO NOT REMOVE" in row["attribution"]


def test_reference_display_uses_surah_name(built):
    out, _ = built
    rec = db.get_record(db.connect(out), "quran:112:1")
    assert rec.reference_display == "Al-Ikhlas 112:1"


def test_fts_is_populated(built):
    out, _ = built
    assert db.fts_candidates(db.connect(out), "الصمد") != []


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


def test_fts_indexes_translation_text(built_with_translation):
    # Proves rebuild_fts ran AFTER the translations were inserted, not before.
    out, _ = built_with_translation
    results = db.fts_candidates(db.connect(out), "beneficent")
    assert any(c.record.id == "quran:1:1" for c in results)


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
    out = tmp_path_factory.mktemp("real-corpus") / "corpus.db"
    report = out.parent / "hadith-noise-report.md"
    stats = build_corpus(REAL_LOCKFILE, out, REAL_CACHE, noise_report=report)
    return out, stats, report


def test_builds_hadith_records_with_matn_as_the_scored_text(real_corpus):
    out, _, _ = real_corpus
    conn = db.connect(out)
    n = conn.execute("SELECT count(*) FROM records WHERE kind='hadith'").fetchone()[0]
    assert n == 7129
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
    assert len(rows) == 7129
    for row in rows:
        for form in ("light", "standard", "aggressive"):
            assert row[f"norm_{form}"] == normalize(row["text_ar"], form), row["id"]


def test_corpus_holds_both_the_quran_and_the_hadith(real_corpus):
    out, _, _ = real_corpus
    counts = dict(db.connect(out).execute(
        "SELECT kind, count(*) FROM records GROUP BY kind").fetchall())
    assert counts == {"ayah": 6236, "hadith": 7129}


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
    # again. Five printed numbers appear twice in this edition.
    out, _, _ = real_corpus
    rows = db.connect(out).execute(
        "SELECT reference_display FROM records WHERE kind='hadith'").fetchall()
    refs = [r[0] for r in rows]
    assert len(refs) == 7129
    assert len(set(refs)) == 7129


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
        content_sha256="0" * 64, modifications="none", expected_records=2)
    with pytest.raises(BuildError, match="Sahih al-Bukhari 7"):
        _hadith_records(parsed, locked)


# --- fix round 1: secondary narrations are stored, not scored --------------

def test_the_appended_narrations_are_stored_but_never_scored(real_corpus):
    """393 records carry an addendum. It is in the row and out of THAT score.

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
    assert n == 393
    rec = db.get_record(conn, "hadith:bukhari:22")
    assert rec.addenda_ar and _HADDATHANA in rec.addenda_ar
    assert _HADDATHANA not in rec.text_ar
    assert rec.text_ar_sha256 == hashlib.sha256(
        rec.text_ar.encode("utf-8")).hexdigest()
    for form in ("light", "standard", "aggressive"):
        assert getattr(rec, f"norm_{form}") == normalize(rec.text_ar, form)
        assert _HADDATHANA not in getattr(rec, f"norm_{form}")


def test_no_addendum_reaches_the_primary_representation(real_corpus):
    """Exhaustive over all 393, in both the stored and the indexed text.

    The other half of the guarantee is
    test_fts_indexes_the_record_norms_and_nothing_else, which pins each index
    row to the column it claims to index. Together: the addendum is not in the
    primary's norms, and the primary index row is nothing but those norms.

    392, not 393: hadith 237 both carries an addendum and is on the
    unscorable audit list (its matn is a "bayna" clause ending at the
    chain-transfer mark), so it has no index row at all. The two counts are
    asserted separately rather than relaxed into one, so that a record
    silently falling out of the index cannot hide inside this total.
    """
    out, _, _ = real_corpus
    conn = db.connect(out)
    assert conn.execute(
        "SELECT count(*) FROM records WHERE addenda_ar IS NOT NULL"
        " AND unscorable_reason IS NOT NULL").fetchone()[0] == 1
    rows = conn.execute(
        "SELECT r.id, r.text_ar, r.addenda_ar, f.norm_standard,"
        "       f.norm_aggressive FROM records r"
        " JOIN records_fts f ON f.record_id = r.id AND f.variant = 'primary'"
        " WHERE r.addenda_ar IS NOT NULL").fetchall()
    assert len(rows) == 392
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
    """
    out, _, _ = real_corpus
    conn = db.connect(out)
    rows = conn.execute(
        "SELECT r.id, r.text_ar, r.addenda_ar, r.unscorable_reason,"
        "       v.variant, v.text_ar AS whole, v.norm_light, v.norm_standard,"
        "       v.norm_aggressive FROM records r"
        " LEFT JOIN record_variants v ON v.record_id = r.id"
        " WHERE r.addenda_ar IS NOT NULL").fetchall()
    assert len(rows) == 393
    checked = 0
    for row in rows:
        if row["unscorable_reason"]:
            assert row["variant"] is None, row["id"]   # excluded from both
            continue
        assert row["variant"] == "full", row["id"]
        assert row["whole"] == row["text_ar"] + " " + row["addenda_ar"], row["id"]
        for form in ("light", "standard", "aggressive"):
            assert row[f"norm_{form}"] == normalize(row["whole"], form), row["id"]
        checked += 1
    assert checked == 392


def test_a_record_with_no_addendum_has_no_second_representation(real_corpus):
    """Nothing is indexed twice for no reason: the full text of an uncut
    record IS its primary, and a duplicate row would let one record occupy two
    places in a tie set."""
    out, _, _ = real_corpus
    n = db.connect(out).execute(
        "SELECT count(*) FROM record_variants v JOIN records r ON r.id = v.record_id"
        " WHERE r.addenda_ar IS NULL").fetchone()[0]
    assert n == 0


def test_an_unscorable_record_is_excluded_from_both_representations(real_corpus):
    """237 carries an addendum and is on the unscorable audit list. Neither
    its primary nor its full text may be a match candidate."""
    out, _, _ = real_corpus
    conn = db.connect(out)
    rec = db.get_record(conn, "hadith:bukhari:237")
    assert rec.addenda_ar and rec.unscorable_reason
    assert conn.execute(
        "SELECT count(*) FROM record_variants WHERE record_id = 'hadith:bukhari:237'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM records_fts WHERE record_id = 'hadith:bukhari:237'"
    ).fetchone()[0] == 0


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
        content_sha256="0" * 64, modifications="none", expected_records=1)
    with pytest.raises(BuildError, match="empty scored text"):
        _hadith_records(parsed, locked)


# --- fix round 3: editorial pointers are kept, displayed, never scored -----

# The audited list, restated here independently of the parser's copy. If the
# two ever disagree, one of them was edited without the audit being redone.
_UNSCORABLE_IDS = frozenset(f"hadith:bukhari:{n}" for n in (
    "127", "237", "335", "394", "549", "557", "1379", "1915", "2483", "3457",
    "3750", "3777", "3801", "3957", "4540", "5454", "5837",
))
# Famous short matns, read in the source and ruled genuine: "war is deceit",
# "the moon split", "a rich man's delay is oppression", "every kindness is
# charity". They are the guard against a length heuristic creeping back in.
_GENUINE_SHORT_IDS = tuple(f"hadith:bukhari:{n}" for n in
                           ("2866", "3658", "2270", "5675"))


def test_editorial_pointers_are_kept_but_never_scored(real_corpus):
    out, _, _ = real_corpus
    conn = db.connect(out)
    flagged = {r[0] for r in conn.execute(
        "SELECT id FROM records WHERE unscorable_reason IS NOT NULL").fetchall()}
    assert flagged == set(_UNSCORABLE_IDS)
    for record_id in sorted(_UNSCORABLE_IDS):
        rec = db.get_record(conn, record_id)
        # Nothing is deleted: the record stays, keeps its citation, and keeps
        # the edition's words. Only its scorability changes.
        assert rec is not None, record_id
        assert rec.text_ar.strip(), record_id
        assert rec.reference_display.startswith("Sahih al-Bukhari "), record_id
        assert rec.unscorable_reason, record_id


def test_no_unscorable_record_is_in_the_search_index(real_corpus):
    out, _, _ = real_corpus
    n = db.connect(out).execute(
        "SELECT count(*) FROM records_fts f JOIN records r ON r.id = f.record_id"
        " WHERE r.unscorable_reason IS NOT NULL").fetchone()[0]
    assert n == 0


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
        content_sha256="0" * 64, modifications="none", expected_records=1)
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
    from sanad_ingest.build import BuildError, _hadith_records
    from sanad_ingest.lockfile import LockedSource
    from sanad_ingest.openiti import _NEVER_CUT, _UNSCORABLE, HadithUnit, ParsedOpeniti

    def _unit(record_id: str) -> HadithUnit:
        no = record_id.rsplit(":", 1)[1]
        return HadithUnit(hadith_no=no, record_id=record_id, is_repeat=False,
                          kitab_no=1, kitab_ar="k", bab_ar="b",
                          isnad_ar="i", matn_ar="m", addenda_ar=None)

    # everything on both lists except hadith 632, which this corpus has lost
    ids = sorted(set(_UNSCORABLE) | (set(_NEVER_CUT) - {"hadith:bukhari:632"}))
    assert "hadith:bukhari:6136" in ids, "only 632 may be missing"
    parsed = ParsedOpeniti(units=[_unit(i) for i in ids], attribution="",
                           content_sha256="0" * 64, noisy=[])
    locked = LockedSource(
        id="x", kind="hadith-arabic", format="openiti-markdown", title="X",
        url="https://example.invalid/x", license_id="public-domain",
        content_sha256="0" * 64, modifications="none", expected_records=len(ids))
    with pytest.raises(BuildError, match="hadith:bukhari:632"):
        _hadith_records(parsed, locked)
