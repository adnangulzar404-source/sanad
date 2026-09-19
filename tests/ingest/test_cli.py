from sanad_ingest import cli


def test_malformed_download_reports_error_not_traceback(tmp_path, monkeypatch, capsys):
    # cli.main used to catch LockfileError and HashMismatch but not
    # TanzilParseError, so a malformed download (bad format, or a source
    # whose declared format doesn't match its actual shape) surfaced as an
    # uncaught traceback instead of the same "error: ..." message every
    # other build failure produces.
    lock = tmp_path / "corpus.lock.toml"
    lock.write_text(
        'lockfile_version = 1\n[[source]]\n'
        'id = "bad"\nkind = "quran-arabic"\nformat = "txt-2"\n'
        'title = "t"\nurl = "https://example.invalid/bad"\n'
        'license_id = "CC-BY-3.0"\n'
        f'content_sha256 = "{"0" * 64}"\nexpected_lines = 1\nmodifications = "none"\n',
        encoding="utf-8")

    monkeypatch.setattr(
        "sanad_ingest.fetch._download", lambda url: "not a valid tanzil line\n")

    exit_code = cli.main([
        "build",
        "--lockfile", str(lock),
        "--out", str(tmp_path / "out.db"),
        "--cache", str(tmp_path / "cache"),
    ])

    assert exit_code == 1
    assert "error:" in capsys.readouterr().err
