from tm_rag.index import build_index, search


def test_target_lang_filter_returns_only_that_language(mini_data_dir, tmp_path):
    qdrant = tmp_path / "q"
    build_index(mini_data_dir / "tm.tmx", qdrant)

    matches = search("settings", k=5, qdrant_path=qdrant, target_lang="zh-TW")
    assert matches
    assert all(m.unit.tgt_lang == "zh-TW" for m in matches)
    assert {m.unit.id for m in matches} == {"u2@zh-TW"}

    matches = search("settings", k=5, qdrant_path=qdrant, target_lang="zh-CN")
    assert matches
    assert all(m.unit.tgt_lang == "zh-CN" for m in matches)
    assert "u2@zh-TW" not in {m.unit.id for m in matches}
    assert "u2" in {m.unit.id for m in matches}


def test_hybrid_search_returns_fused_scores_in_unit_interval(mini_data_dir, tmp_path):
    qdrant = tmp_path / "q"
    build_index(mini_data_dir / "tm.tmx", qdrant)

    matches = search("save my progress", k=3, qdrant_path=qdrant, hybrid=True)
    assert len(matches) == 3
    assert all(0.0 < m.score <= 1.0 for m in matches)
    scores = [m.score for m in matches]
    assert scores == sorted(scores, reverse=True)
    assert matches[0].unit.id == "u4"


def test_hybrid_with_target_lang_filters_and_fuses(mini_data_dir, tmp_path):
    qdrant = tmp_path / "q"
    build_index(mini_data_dir / "tm.tmx", qdrant)

    matches = search("settings", k=5, qdrant_path=qdrant, hybrid=True, target_lang="zh-CN")
    assert matches
    assert all(m.unit.tgt_lang == "zh-CN" for m in matches)
    assert all(0.0 < m.score <= 1.0 for m in matches)
    assert matches[0].unit.id == "u2"


def test_hybrid_keyword_query_ranks_exact_source_first(mini_data_dir, tmp_path):
    qdrant = tmp_path / "q"
    build_index(mini_data_dir / "tm.tmx", qdrant)

    matches = search("quit game", k=2, qdrant_path=qdrant, hybrid=True)
    assert matches[0].unit.id == "u5"
