FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml ./
COPY api ./api
COPY ingest ./ingest
COPY eval ./eval

# `sanad-ingest` is installed so the corpus can be rebuilt on demand (e.g.
# `docker run sanad sanad-ingest build --out /tmp/x.db`), but this Dockerfile
# never invokes it: doing so at build time would need outbound network access
# to tanzil.net and would make the image non-hermetic. The corpus is
# committed, content-hash-verified data (see data/sanad-quran.db and
# ingest/corpus.lock.toml) -- it is copied into the image below, not built.
RUN pip install --no-cache-dir -e "."

# The corpus: shipped, read-only data. Copied verbatim, never rebuilt here.
COPY data/sanad-quran.db /app/data/sanad-quran.db

ENV SANAD_DB=/app/data/sanad-quran.db

# The audit log is generated, writable state -- never the corpus above,
# which the API opens with SQLite's `mode=ro` and must never be written to
# (see api/sanad/api/app.py's _open_corpus_conn). This default path lives in
# the container's writable layer, so audit rows do NOT survive a
# `docker rm`/recreate. A deployment that wants audit history to persist
# across restarts must mount this path (or its parent directory) as a
# volume, e.g. `docker run -v sanad-audit-data:/app/data/audit
# -e SANAD_AUDIT_DB=/app/data/audit/sanad-audit.db ...`.
ENV SANAD_AUDIT_DB=/app/data/sanad-audit.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://localhost:8000/api/health').status_code==200 else 1)"

CMD ["uvicorn", "sanad.api.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
