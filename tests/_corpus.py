"""Shared materialized-DB path for every test that needs derived data.

`data/sanad-quran.db` is SOURCE-ONLY as of Stage A3 Task 4: `norm_light`,
`norm_standard`, `norm_aggressive` and `text_ar_sha256` are NULL, and there is
no `record_variants` table and no `records_fts` index. Almost every test in
this suite verifies against derived data (norms, the FTS index, the `full`
record variant), so a test that opens the committed file directly either gets
a `pydantic.ValidationError` (a NULL where a `Record` field is required) or
`sqlite3.OperationalError: no such table: records_fts`.

This module gives every test file that needs derived data the SAME
materialized DB, built once and cached on disk, rather than each test module
paying `materialize()`'s cost (or worse, opening the source-only file
directly). It is deliberately just a path constant plus the side effect of
building it -- no pytest fixture machinery -- so it can be imported equally
from a test module, from `tests/conftest.py` at collection time, or from a
plain script.

`MATERIALIZED_DB` is rebuilt only when the cache is missing or older than the
source DB's mtime, so swapping in a fresh `sanad-quran.db` is picked up
automatically and a no-op `pytest` re-run pays nothing.

A test that instead wants to assert something about the committed file being
source-only (e.g. "norms are NULL", "records_fts does not exist") must keep
reading `"data/sanad-quran.db"` literally -- that is the file under test in
those cases, not a stand-in for the materialized one.
"""
from __future__ import annotations

import os
from pathlib import Path

from sanad_ingest.materialize import materialize

_SOURCE_DB = Path("data/sanad-quran.db")
_CACHE_DIR = Path(".corpus-cache")
_CACHE_DB = _CACHE_DIR / "sanad-materialized.db"


def _build_if_stale() -> Path:
    """Materialize `_SOURCE_DB` into the cache if it is missing or stale.

    The freshness check is a plain mtime comparison -- good enough for a
    single developer machine or CI runner, which is the whole of this
    project's build environment today.

    The write itself is race-safe against concurrent pytest processes: each
    caller materializes into its own `*.db.tmp.<pid>` file, and only the
    final `os.replace` -- atomic on the same filesystem -- touches the shared
    cache path. Two processes racing each other each produce a byte-identical
    output (`materialize` is deterministic; see
    `tests/ingest/test_materialize.py::test_materialize_is_deterministic`),
    so whichever replace wins, the cache is correct.
    """
    stale = (
        not _CACHE_DB.is_file()
        or _CACHE_DB.stat().st_mtime < _SOURCE_DB.stat().st_mtime
    )
    if stale:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_DIR / f"sanad-materialized.db.tmp.{os.getpid()}"
        materialize(str(_SOURCE_DB), str(tmp))
        os.replace(tmp, _CACHE_DB)
    return _CACHE_DB


MATERIALIZED_DB = str(_build_if_stale())
