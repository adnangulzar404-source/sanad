from sanad.retrieve.fuse import rrf_fuse

def test_rrf_rewards_agreement_across_lists():
    lexical = ["a", "b", "c"]
    vector = ["b", "a", "d"]
    fused = [rid for rid, _ in rrf_fuse([lexical, vector])]
    # b and a appear high in both; they lead. d and c appear in one each.
    assert fused[:2] == ["a", "b"] or fused[:2] == ["b", "a"]
    assert set(fused) == {"a", "b", "c", "d"}

def test_rrf_single_list_preserves_order():
    assert [r for r, _ in rrf_fuse([["x", "y", "z"]])] == ["x", "y", "z"]

def test_rrf_empty_input_is_empty():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []
