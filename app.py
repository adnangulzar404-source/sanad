"""Vercel entrypoint.

Vercel's Python runtime loads a top-level `app` from app.py at the project
root. Sanad's application lives behind a factory in api/sanad/api/app.py, so
this module is a shim and nothing more — no logic belongs here.

The audit log must point at /tmp: serverless filesystems are read-only
everywhere else. The corpus is already opened read-only, so it is unaffected.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "api"))

os.environ.setdefault("SANAD_AUDIT_DB", "/tmp/sanad-audit.db")

from sanad.api.app import create_app  # noqa: E402

app = create_app()
