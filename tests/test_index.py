from tm_rag.index import build_index, index_exists, search


def test_build_and_search_on_tiny_fixture(mini_data_dir, tmp_path):
    qdrant = tmp_path / "q"
    n = build_index(mini_data_dir / "tm.tmx", qdrant)
    assert n == 7
    assert index_exists(qdrant)

    matches = search("start a brand new game", k=3, qdrant_path=qdrant)
    assert len(matches) == 3
    assert matches[0].unit.id == "u1"
    assert matches[0].unit.target == "新游戏"
    assert 0.0 < matches[0].score <= 1.0
    scores = [m.score for m in matches]
    assert scores == sorted(scores, reverse=True)


def test_search_by_meaning_not_keywords(mini_data_dir, tmp_path):
    qdrant = tmp_path / "q"
    build_index(mini_data_dir / "tm.tmx", qdrant)
    matches = search("leave the game and go to desktop", k=1, qdrant_path=qdrant)
    assert matches[0].unit.id == "u5"


def test_search_returns_zh_tw_variant_too(mini_data_dir, tmp_path):
    qdrant = tmp_path / "q"
    build_index(mini_data_dir / "tm.tmx", qdrant)
    matches = search("settings", k=5, qdrant_path=qdrant)
    ids = {m.unit.id for m in matches}
    assert "u2" in ids and "u2@zh-TW" in ids


def test_rebuild_is_idempotent(mini_data_dir, tmp_path):
    qdrant = tmp_path / "q"
    build_index(mini_data_dir / "tm.tmx", qdrant)
    build_index(mini_data_dir / "tm.tmx", qdrant)
    matches = search("save my progress", k=1, qdrant_path=qdrant)
    assert matches[0].unit.id == "u4"


def test_search_on_missing_index_returns_empty(tmp_path):
    assert search("anything", k=3, qdrant_path=tmp_path / "nope") == []
    assert not index_exists(tmp_path / "nope")
