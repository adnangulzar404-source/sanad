import httpx
from sanad.retrieve.voyage import embed_texts, hamming_topk, VoyageError

def _fake_client(payload, status=200):
    def handler(request):
        return httpx.Response(status, json=payload)
    return httpx.Client(transport=httpx.MockTransport(handler))

def test_embed_texts_packs_binary_vectors_in_order():
    # Voyage returns one 1024-bit vector per text as 128 signed int8 bytes.
    payload = {"data": [
        {"index": 0, "embedding": [1] * 128},
        {"index": 1, "embedding": [-1] * 128},
    ]}
    out = embed_texts(["a", "b"], input_type="document", key="k",
                      client=_fake_client(payload))
    assert len(out) == 2 and all(len(v) == 128 for v in out)

def test_embed_texts_reorders_by_index():
    payload = {"data": [
        {"index": 1, "embedding": [0] * 128},
        {"index": 0, "embedding": [127] * 128},
    ]}
    out = embed_texts(["first", "second"], input_type="document", key="k",
                      client=_fake_client(payload))
    assert out[0] == bytes([127] * 128) and out[1] == bytes([0] * 128)

def test_embed_texts_raises_on_http_error():
    try:
        embed_texts(["a"], input_type="document", key="k",
                    client=_fake_client({"error": "bad"}, status=401))
        assert False, "expected VoyageError"
    except VoyageError:
        pass

def test_hamming_topk_orders_by_distance():
    q = bytes([0b00000000]) + bytes(127)
    corpus = [
        ("same", bytes([0b00000000]) + bytes(127)),   # distance 0
        ("one",  bytes([0b00000001]) + bytes(127)),   # distance 1
        ("three", bytes([0b00000111]) + bytes(127)),  # distance 3
    ]
    got = hamming_topk(q, corpus, k=2)
    assert [rid for rid, _ in got] == ["same", "one"]
    assert got[0][1] == 0 and got[1][1] == 1
