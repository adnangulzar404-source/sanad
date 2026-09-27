"""The materialized-DB fixture itself: does `tests._corpus` actually derive?

Every other migrated test trusts `MATERIALIZED_DB` implicitly by using it.
This is the one place that checks the fixture's own promise directly --
norms are non-NULL, the FTS index and `record_variants` exist -- so a
regression in `tests/_corpus.py` (a stale cache never rebuilt, a materialize
call that silently no-ops) fails here first instead of surfacing as 107
unrelated-looking failures across the rest of the suite again.
"""
import sqlite3

from tests._corpus import MATERIALIZED_DB


def test_materialized_fixture_has_norms():
    n = sqlite3.connect(MATERIALIZED_DB).execute(
        "SELECT COUNT(*) FROM records WHERE norm_standard IS NOT NULL").fetchone()[0]
    assert n > 0


def test_materialized_fixture_has_fts_and_variants():
    conn = sqlite3.connect(MATERIALIZED_DB)
    assert conn.execute("SELECT COUNT(*) FROM records_fts").fetchone()[0] > 0
    assert conn.execute("SELECT COUNT(*) FROM record_variants").fetchone()[0] > 0


def test_materialized_fixture_is_cached_on_disk():
    from pathlib import Path
    assert Path(MATERIALIZED_DB) == Path(".corpus-cache/sanad-materialized.db")
    assert Path(MATERIALIZED_DB).is_file()
