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

from tests._corpus import MATERIALIZED_DB

# `SANAD_DB` is set here, at conftest MODULE import time -- not inside a
# fixture -- because pytest imports `tests/conftest.py` before it collects or
# runs a single test, which is earlier than any fixture (session-scoped or
# otherwise) can run. `sanad.api.app.create_app()` (and the root `app.py`
# Vercel shim, which calls it at ITS OWN import time) resolve the corpus path
# by calling `settings.resolve_db_path()` lazily, inside `create_app()` --
# never at `sanad.api.app` import time -- so the only requirement is that
# `SANAD_DB` be set before the first `create_app()` call anywhere in the
# suite. A module-level assignment in this conftest -- which pytest always
# imports first -- is the earliest possible point, strictly before any
# fixture-based alternative could fire. Every test that constructs the app
# (`TestClient(create_app())`, or `import app as entrypoint`) therefore opens the
# MATERIALIZED database, never the source-only committed one -- verified by
# `tests/api/test_routes.py` and `tests/api/test_ask_route.py` going green.
#
# Not unconditional: a caller who deliberately exported `SANAD_DB` before
# invoking pytest (e.g. to point the suite at some other corpus) is left
# alone rather than overridden.
os.environ.setdefault("SANAD_DB", MATERIALIZED_DB)


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
