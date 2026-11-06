import json

from tm_rag.cli import main


def test_cli_index_search_translate_eval_smoke(mini_data_dir, tmp_path, capsys):
    qdrant = str(tmp_path / "q")
    data = str(mini_data_dir)

    assert main(["index", "--data-dir", data, "--qdrant", qdrant]) == 0
    out = capsys.readouterr().out
    assert "Indexed 7 units" in out

    assert main(["search", "begin a new adventure", "--k", "2", "--data-dir", data, "--qdrant", qdrant]) == 0
    out = capsys.readouterr().out
    assert "u1" in out and "新游戏" in out

    assert main(["translate", "New Game", "--data-dir", data, "--qdrant", qdrant]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["provider"] == "mock"
    assert payload["result"]["translation"] == "新游戏"
    assert payload["qa_passed"] is True
    assert payload["result"]["notes"]

    results_path = tmp_path / "results" / "eval.json"
    assert (
        main(
            [
                "eval",
                "--k", "1", "3",
                "--data-dir", data,
                "--qdrant", qdrant,
                "--results", str(results_path),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "recall@k" in out
    result = json.loads(results_path.read_text(encoding="utf-8"))
    assert result["n_gold"] == 3
    assert result["n_units"] == 7
    assert set(result["recall_at_k"]) == {"1", "3"}
    assert 0.0 <= result["mrr"] <= 1.0
    assert 0.0 <= result["qa_pass_rate"] <= 1.0


def test_cli_translate_reports_qa_failure_honestly(mini_data_dir, tmp_path, capsys):
    qdrant = str(tmp_path / "q")
    data = str(mini_data_dir)
    main(["index", "--data-dir", data, "--qdrant", qdrant])
    capsys.readouterr()
    # "Welcome, {name}!" retrieves u3 whose target keeps {name}; break it via a source whose
    # closest match drops the placeholder: query with placeholder, index has none matching
    assert main(["translate", "Hello there, {player}!", "--data-dir", data, "--qdrant", qdrant]) == 0
    payload = json.loads(capsys.readouterr().out)
    checks = {f["check"]: f["passed"] for f in payload["qa"]}
    assert checks["placeholder_preservation"] is False
    assert payload["qa_passed"] is False
