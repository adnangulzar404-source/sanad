"""Session-wide test isolation guard.

Any test that calls `create_app()` opens a connection to whatever
`settings.resolve_audit_db_path()` resolves to at that moment. Without this
fixture, a test that forgets to set `SANAD_AUDIT_DB` falls through to the
default, `data/sanad-audit.db` -- a real path next to the corpus. An earlier
revision of this suite hit exactly that: running the tests dirtied a
git-tracked binary. `.gitignore` now excludes that path too, but a gitignore
entry only hides the symptom -- it does not stop a stray test from writing
audit rows into a real, shared database file.

This autouse, session-scoped fixture makes that failure mode structurally
impossible: `SANAD_AUDIT_DB` is pinned to a throwaway directory for the
entire life of the test session, before any test module's own fixtures run,
so there is no window in which a missing override could fall through to the
real default.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolate_audit_db():
    with tempfile.TemporaryDirectory(prefix="sanad-audit-test-") as tmp:
        previous = os.environ.get("SANAD_AUDIT_DB")
        os.environ["SANAD_AUDIT_DB"] = str(Path(tmp) / "sanad-audit-session.db")
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("SANAD_AUDIT_DB", None)
            else:
                os.environ["SANAD_AUDIT_DB"] = previous
