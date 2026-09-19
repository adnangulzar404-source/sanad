import pytest
from sanad_ingest.lockfile import LockfileError, load_lockfile

REAL = "ingest/corpus.lock.toml"


def test_loads_the_real_lockfile():
    sources = load_lockfile(REAL)
    assert len(sources) == 2
    by_id = {s.id: s for s in sources}

    arabic = by_id["tanzil-uthmani-1.1"]
    assert arabic.expected_lines == 6236
    assert arabic.license_id == "CC-BY-3.0"
    assert len(arabic.content_sha256) == 64

    translation = by_id["tanzil-en-pickthall"]
    assert translation.kind == "quran-translation"
    assert translation.expected_lines == 6236
    assert translation.license_id == "public-domain"
    assert len(translation.content_sha256) == 64


def test_rejects_missing_required_field(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text('lockfile_version = 1\n[[source]]\nid = "x"\n', encoding="utf-8")
    with pytest.raises(LockfileError, match="missing"):
        load_lockfile(p)


def test_rejects_malformed_sha256(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text(
        'lockfile_version = 1\n[[source]]\n'
        'id="x"\nkind="quran-arabic"\ntitle="t"\nurl="u"\n'
        'license_id="CC-BY-3.0"\ncontent_sha256="nothex"\n'
        'expected_lines=1\nmodifications="none"\n', encoding="utf-8")
    with pytest.raises(LockfileError, match="sha256"):
        load_lockfile(p)


def test_rejects_unknown_lockfile_version(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text("lockfile_version = 99\n", encoding="utf-8")
    with pytest.raises(LockfileError, match="version"):
        load_lockfile(p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(LockfileError, match="not found"):
        load_lockfile(tmp_path / "nope.toml")
