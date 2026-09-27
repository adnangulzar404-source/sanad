import subprocess
import sqlite3


def test_cli_materialize(tmp_path):
    src = tmp_path / "src.db"
    out = tmp_path / "out.db"
    # Build a source-only src via the strip helper reused from test_materialize
    from tests.ingest.test_materialize import _strip_to_source
    _strip_to_source("data/sanad-quran.db", str(src))
    r = subprocess.run(["sanad-ingest", "materialize", "--in", str(src),
                        "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert sqlite3.connect(str(out)).execute(
        "SELECT COUNT(*) FROM records WHERE norm_standard IS NOT NULL"
    ).fetchone()[0] > 0
