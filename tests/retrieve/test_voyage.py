import httpx
from sanad.retrieve.voyage import embed_texts, hamming_topk, VoyageError, VOYAGE_MAX_BATCH

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

def test_embed_texts_preserves_order_across_multiple_batches():
    # Verify embed_texts maintains correct vector order when VOYAGE_MAX_BATCH batching occurs.
    # With 1001 texts and VOYAGE_MAX_BATCH=1000, two API calls are made.
    # Each response has batch-relative indices (0-999, then 0).
    # Embed absolute position (index within all texts) in each vector's first two bytes.

    num_texts = VOYAGE_MAX_BATCH + 1  # 1001 texts
    batch_call_count = [0]

    def handler(request):
        batch_num = batch_call_count[0]
        batch_start_idx = batch_num * VOYAGE_MAX_BATCH
        batch_call_count[0] += 1

        # Generate embeddings for this batch, encoding absolute position
        data = []
        for batch_idx in range(VOYAGE_MAX_BATCH):
            abs_idx = batch_start_idx + batch_idx
            if abs_idx >= num_texts:
                break
            # Encode absolute position: [high byte, low byte, 0, 0, ...]
            embedding = [abs_idx // 256, abs_idx % 256] + [0] * 126
            data.append({"index": batch_idx, "embedding": embedding})

        return httpx.Response(200, json={"data": data})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    texts = [f"text_{i}" for i in range(num_texts)]
    out = embed_texts(texts, input_type="document", key="k", client=client)

    # Verify all vectors returned
    assert len(out) == num_texts, f"Expected {num_texts} vectors, got {len(out)}"

    # Verify order by decoding absolute position from each embedding
    for abs_idx, vec in enumerate(out):
        expected_high = abs_idx // 256
        expected_low = abs_idx % 256
        actual_high = vec[0]
        actual_low = vec[1]
        assert actual_high == expected_high and actual_low == expected_low, \
            f"Vector at position {abs_idx}: expected ({expected_high}, {expected_low}), got ({actual_high}, {actual_low})"

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
