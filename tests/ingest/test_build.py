import hashlib
from pathlib import Path

import pytest
from sanad.corpus import db
from sanad_ingest.build import build_corpus

FIXTURE = Path("tests/fixtures/tanzil_excerpt.txt")
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
        'id = "tanzil-uthmani-1.1"\nkind = "quran-arabic"\n'
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
        'id = "tanzil-uthmani-1.1"\nkind = "quran-arabic"\n'
        'title = "Tanzil Uthmani"\npublisher = "Tanzil Project"\n'
        'edition = "1.1"\n'
        f'url = "{_ARABIC_URL}"\n'
        'license_id = "CC-BY-3.0"\nlicense_url = "https://tanzil.net/docs/text_license"\n'
        f'content_sha256 = "{sha_ar}"\nexpected_lines = 4\nmodifications = "none"\n'
        '\n'
        '[[source]]\n'
        'id = "tanzil-en-pickthall"\nkind = "quran-translation"\n'
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
    assert any(r.id == "quran:1:1" for r in results)
