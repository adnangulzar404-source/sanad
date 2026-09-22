import re

import pytest
from sanad_ingest.lockfile import LockfileError, load_lockfile

REAL = "ingest/corpus.lock.toml"


def test_loads_the_real_lockfile():
    sources = load_lockfile(REAL)
    assert len(sources) == 3
    by_id = {s.id: s for s in sources}

    arabic = by_id["tanzil-uthmani-1.1"]
    assert arabic.expected_lines == 6236
    assert arabic.license_id == "CC-BY-3.0"
    assert len(arabic.content_sha256) == 64
    # Not txt-2: that export prepends the Bismillah into ayah 1's text.
    assert arabic.format == "xml"

    translation = by_id["tanzil-en-pickthall"]
    assert translation.kind == "quran-translation"
    assert translation.expected_lines == 6236
    assert translation.license_id == "public-domain"
    assert len(translation.content_sha256) == 64
    assert translation.format == "txt-2"


def test_rejects_missing_required_field(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text('lockfile_version = 1\n[[source]]\nid = "x"\n', encoding="utf-8")
    with pytest.raises(LockfileError, match="missing"):
        load_lockfile(p)


def test_rejects_malformed_sha256(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text(
        'lockfile_version = 1\n[[source]]\n'
        'id="x"\nkind="quran-arabic"\nformat="txt-2"\ntitle="t"\nurl="u"\n'
        'license_id="CC-BY-3.0"\ncontent_sha256="nothex"\n'
        'expected_lines=1\nmodifications="none"\n', encoding="utf-8")
    with pytest.raises(LockfileError, match="sha256"):
        load_lockfile(p)


def test_rejects_unsupported_format(tmp_path):
    # A typo like "xlm" must fail at load time, naming the field and the
    # bad value, rather than silently being treated as txt-2 by whatever
    # dispatch reads `format` downstream.
    p = tmp_path / "bad.toml"
    p.write_text(
        'lockfile_version = 1\n[[source]]\n'
        'id="x"\nkind="quran-arabic"\nformat="xlm"\ntitle="t"\nurl="u"\n'
        'license_id="CC-BY-3.0"\ncontent_sha256="' + "0" * 64 + '"\n'
        'expected_lines=1\nmodifications="none"\n', encoding="utf-8")
    with pytest.raises(LockfileError, match="format"):
        load_lockfile(p)


def test_rejects_unknown_lockfile_version(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text("lockfile_version = 99\n", encoding="utf-8")
    with pytest.raises(LockfileError, match="version"):
        load_lockfile(p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(LockfileError, match="not found"):
        load_lockfile(tmp_path / "nope.toml")


def test_rejects_a_lockfile_with_no_sources(tmp_path):
    # A syntactically valid lockfile with zero [[source]] entries must not
    # silently return [] -- build_corpus would then emit a valid-looking but
    # empty database with no complaint. Naming the file makes the error
    # actionable rather than a mystery downstream.
    p = tmp_path / "empty.toml"
    p.write_text("lockfile_version = 1\n", encoding="utf-8")
    with pytest.raises(LockfileError, match=re.escape(str(p))):
        load_lockfile(p)


def test_accepts_the_openiti_markdown_bukhari_entry():
    srcs = load_lockfile(REAL)
    bukhari = [s for s in srcs if s.id == "openiti-bukhari-jk000110"]
    assert len(bukhari) == 1, "the Bukhari source must be pinned in the lockfile"
    b = bukhari[0]
    assert b.format == "openiti-markdown"
    assert b.kind == "hadith-arabic"
    assert b.license_id == "public-domain"
    assert b.expected_records == 7129
    assert b.content_sha256 == (
        "69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7"
    )


def test_rejects_openiti_markdown_entry_missing_expected_records(tmp_path):
    # An openiti-markdown entry that supplies the WRONG count field
    # (expected_lines, the Tanzil one) instead of its own (expected_records)
    # must be rejected, not silently accepted with an unchecked count --
    # that is precisely the gap R2 exists to close.
    p = tmp_path / "bad.toml"
    p.write_text(
        'lockfile_version = 1\n[[source]]\n'
        'id="openiti-x"\nkind="hadith-arabic"\nformat="openiti-markdown"\n'
        'title="t"\nurl="u"\nlicense_id="public-domain"\n'
        'content_sha256="' + "0" * 64 + '"\n'
        'expected_lines=1\nmodifications="none"\n', encoding="utf-8")
    with pytest.raises(LockfileError, match="expected_records") as exc:
        load_lockfile(p)
    assert "openiti-x" in str(exc.value)


def test_rejects_tanzil_entry_missing_expected_lines(tmp_path):
    # The mirror image: an xml/txt-2 entry that supplies expected_records
    # (the hadith one) instead of expected_lines must also be rejected.
    p = tmp_path / "bad.toml"
    p.write_text(
        'lockfile_version = 1\n[[source]]\n'
        'id="tanzil-x"\nkind="quran-arabic"\nformat="txt-2"\n'
        'title="t"\nurl="u"\nlicense_id="CC-BY-3.0"\n'
        'content_sha256="' + "0" * 64 + '"\n'
        'expected_records=1\nmodifications="none"\n', encoding="utf-8")
    with pytest.raises(LockfileError, match="expected_lines") as exc:
        load_lockfile(p)
    assert "tanzil-x" in str(exc.value)


def test_openiti_bukhari_url_and_hash_are_pinned():
    """The commit SHA pin is outstanding (see the xfail'd test below); until
    it lands, verify what we *can* verify: the URL names the right OpenITI
    path and the content hash is the one measured from the real download."""
    srcs = load_lockfile(REAL)
    b = next(s for s in srcs if s.id == "openiti-bukhari-jk000110")
    assert b.url.startswith("https://raw.githubusercontent.com/OpenITI/0275AH/")
    assert (
        "data/0256Bukhari/0256Bukhari.Sahih/"
        "0256Bukhari.Sahih.JK000110-ara1.completed" in b.url
    )
    assert b.content_sha256 == (
        "69e95684acfde24171d29dd7ba43ff2c8f9b54ade5e3ab0a73899c06671082b7"
    )


@pytest.mark.xfail(
    reason=(
        "Commit pin outstanding: anonymous GitHub API calls are rate-limited "
        "from this network and `gh` has no valid credentials here (401 Bad "
        "credentials), so the commit SHA for OpenITI/0275AH's Bukhari file "
        "could not be obtained. The lockfile currently points at the "
        "`master` branch instead, which is NOT a real pin -- OpenITI "
        "re-OCRs files in place. TODO: fetch the commit SHA (e.g. via an "
        "authenticated `gh api` call or the file's GitHub History page) and "
        "set `commit`/`url` in ingest/corpus.lock.toml accordingly."
    ),
    strict=True,
)
def test_commit_is_required_for_git_hosted_sources():
    """A branch URL is not a pin: OpenITI re-OCRs files in place."""
    srcs = load_lockfile(REAL)
    b = next(s for s in srcs if s.id == "openiti-bukhari-jk000110")
    assert b.commit and len(b.commit) == 40, "expected a full 40-char commit SHA"
    assert b.commit in b.url, "the fetched URL must embed the pinned commit"
