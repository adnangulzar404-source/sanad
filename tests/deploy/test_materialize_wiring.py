"""Static assertions that the image/bundle build derives the full corpus DB.

Task 6 (A3 spec): the deployed app must never open the committed
source-only DB (`data/sanad-quran.db`) at runtime. Both the Docker image
and the Vercel bundle must run `sanad-ingest materialize` at build time to
derive a full runtime DB, and point `SANAD_DB` at it.

These are text/JSON assertions, not a real Docker/Vercel build (neither is
runnable from this environment) -- but each one is specific enough that
removing the wiring it checks makes the test fail.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _dockerfile_text() -> str:
    return (REPO_ROOT / "Dockerfile").read_text()


def _vercel_config() -> dict:
    return json.loads((REPO_ROOT / "vercel.json").read_text())


def test_dockerfile_materializes():
    txt = _dockerfile_text()
    assert "sanad-ingest materialize" in txt

    # The source-only DB must be the declared input.
    assert "sanad-quran.db" in txt

    # SANAD_DB must be set to the derived full DB, not the source-only one.
    assert "ENV SANAD_DB=/app/data/sanad-full.db" in txt
    assert "ENV SANAD_DB=/app/data/sanad-quran.db" not in txt


def test_dockerfile_materialize_runs_after_install_and_before_copy_use():
    """`sanad-ingest` must be on PATH (pip install already ran) and the
    materialize RUN must reference the same path the COPY step wrote to."""
    txt = _dockerfile_text()

    # Anchor to the actual RUN command, not the first textual occurrence of
    # the phrase (which is the explanatory comment above it) -- otherwise a
    # reorder that moved the RUN ahead of `pip install` would still pass while
    # the real build broke with `sanad-ingest: command not found`.
    materialize_line = next(
        line for line in txt.splitlines()
        if line.strip().startswith("RUN") and "sanad-ingest materialize" in line
    )
    install_idx = txt.index("pip install")
    copy_idx = txt.index("COPY data/sanad-quran.db")
    materialize_idx = txt.index(materialize_line)

    assert install_idx < materialize_idx, "pip install must run before materialize"
    assert copy_idx < materialize_idx, "source DB must be copied before materialize runs"

    # The materialize RUN line itself names both the source and derived paths.
    assert "/app/data/sanad-quran.db" in materialize_line
    assert "/app/data/sanad-full.db" in materialize_line


def test_vercel_build_materializes():
    cfg = _vercel_config()
    build_command = cfg["buildCommand"]

    assert "sanad-ingest materialize" in build_command
    assert "sanad-quran.db" in build_command
    assert "sanad-full.db" in build_command

    # SANAD_DB must be wired (build.env or top-level env) to the full DB,
    # not left unset (which would fall back to resolving the source-only DB).
    env = cfg.get("env", {})
    build_env = cfg.get("build", {}).get("env", {})
    sanad_db = env.get("SANAD_DB") or build_env.get("SANAD_DB")
    assert sanad_db is not None, "SANAD_DB must be set somewhere in vercel.json"
    assert "sanad-full.db" in sanad_db
    assert "sanad-quran.db" not in sanad_db


def test_vercel_full_db_not_excluded_from_function_bundle():
    cfg = _vercel_config()
    exclude = cfg["functions"]["app.py"].get("excludeFiles", "")
    assert "sanad-full.db" not in exclude
    assert "data/**" not in exclude
