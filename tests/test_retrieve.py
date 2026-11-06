from tm_rag.retrieve import (
    bm25_scores,
    build_bm25,
    rank_by_score,
    rrf_fuse,
    tokenize,
)


def test_tokenize_splits_latin_words_and_cjk_chars():
    assert tokenize("New Game 2") == ["new", "game", "2"]
    assert tokenize("保存游戏") == ["保", "存", "游", "戏"]
    assert tokenize("Save 保存") == ["save", "保", "存"]


def test_bm25_ranks_keyword_doc_first():
    docs = ["New Game", "Save Game", "Quit Game"]
    index = build_bm25(docs)
    scores = bm25_scores(index, "save my game")
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]
    assert scores[0] == 0.0 or scores[0] < scores[1]


def test_bm25_no_overlap_gives_zero():
    index = build_bm25(["New Game", "Save Game"])
    assert bm25_scores(index, "zzzz nothing") == [0.0, 0.0]


def test_rank_by_score_orders_desc_and_breaks_ties_by_id():
    assert rank_by_score(["b", "a", "c"], [1.0, 1.0, 2.0]) == ["c", "a", "b"]


def test_rrf_fuse_prefers_items_in_both_rankings():
    fused = rrf_fuse([["a", "b"], ["b", "c"]])
    assert fused[0][0] == "b"
    assert fused[0][1] == 1.0
    ids = [item_id for item_id, _ in fused]
    assert ids == ["b", "a", "c"]


def test_rrf_fuse_scores_stay_in_unit_interval():
    fused = rrf_fuse([["a", "b", "c"], ["c", "b", "a"]], k=60)
    assert all(0.0 < score <= 1.0 for _, score in fused)
    assert fused[0][1] == 1.0


def test_rrf_fuse_empty():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []
