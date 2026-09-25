from __future__ import annotations

import os

import httpx

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-4"
VOYAGE_DIM = 1024
VOYAGE_DTYPE = "binary"
VOYAGE_MAX_BATCH = 1000
_TIMEOUT = 60.0


class VoyageError(Exception):
    pass


def resolve_voyage_key() -> str | None:
    return os.environ.get("VOYAGE_API_KEY") or None


def embed_texts(texts: list[str], *, input_type: str, key: str,
                client: httpx.Client | None = None) -> list[bytes]:
    if input_type not in ("document", "query"):
        raise ValueError(f"input_type must be 'document' or 'query', got {input_type!r}")
    owns = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        out: list[bytes] = []
        for start in range(0, len(texts), VOYAGE_MAX_BATCH):
            batch = texts[start:start + VOYAGE_MAX_BATCH]
            resp = client.post(
                VOYAGE_URL,
                headers={"Authorization": f"Bearer {key}",
                         "content-type": "application/json"},
                json={"input": batch, "model": VOYAGE_MODEL,
                      "output_dtype": VOYAGE_DTYPE, "input_type": input_type})
            if resp.status_code != 200:
                raise VoyageError(f"voyage {resp.status_code}: {resp.text[:200]}")
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            for d in data:
                # signed int8 array -> 128 bytes (two's complement)
                out.append(bytes((x & 0xFF) for x in d["embedding"]))
        return out
    except httpx.HTTPError as exc:
        raise VoyageError(str(exc)) from exc
    finally:
        if owns:
            client.close()


def hamming_topk(query: bytes, corpus: list[tuple[str, bytes]],
                 k: int) -> list[tuple[str, int]]:
    qi = int.from_bytes(query, "big")
    scored = [(rid, (qi ^ int.from_bytes(vec, "big")).bit_count())
              for rid, vec in corpus]
    scored.sort(key=lambda t: (t[1], t[0]))
    return scored[:k]
