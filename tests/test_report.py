import json

import pytest

from tm_rag.cli import main
from tm_rag.report import build_report, parse_markdown_tables, pct

TAG_TMX = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header creationtool="test" segtype="sentence" adminlang="en" srclang="en" datatype="PlainText"/>
  <body>
    <tu tuid="t1">
      <tuv xml:lang="en"><seg>&lt;b&gt;Warning:&lt;/b&gt; a boss is near</seg></tuv>
      <tuv xml:lang="zh-CN"><seg>&lt;b&gt;警告:&lt;/b&gt;首领就在附近</seg></tuv>
      <tuv xml:lang="zh-TW"><seg>&lt;b&gt;警告:&lt;/b&gt;首領就在附近</seg></tuv>
      <tuv xml:lang="th"><seg>&lt;b&gt;คำเตือน:&lt;/b&gt; บอสอยู่ใกล้ๆ</seg></tuv>
    </tu>
    <tu tuid="t2">
      <tuv xml:lang="en"><seg>New Game</seg></tuv>
      <tuv xml:lang="zh-CN"><seg>新游戏</seg></tuv>
      <tuv xml:lang="zh-TW"><seg>新遊戲</seg></tuv>
      <tuv xml:lang="th"><seg>เกมใหม่</seg></tuv>
    </tu>
  </body>
</tmx>
"""

EXPERIMENTS_FIXTURE = """# Experiments fixture

| config | recall@1 | MRR | kept |
|---|---|---|---|
| baseline | 0.7500 | 0.9000 | yes |
"""

EXPERIMENTS_FULL_FIXTURE = """# Experiments fixture with repeated per-experiment k tables

## Experiment 1

| k | recall@k |
|---|----------|
| 1 | 0.7500 |
| 3 | 1.0000 |

## Experiment 2

| k | recall@k |
|---|----------|
| 1 | 0.5000 |
| 3 | 0.6000 |

## Summary

| configuration | recall@1 | kept |
|---|---|---|
| baseline | 0.7500 | yes, best |
"""


def _write_fixture_results(results_dir):
    results_dir.mkdir(parents=True, exist_ok=True)
    retrieval = {
        "config": "baseline",
        "kind": "retrieval",
        "model": "test-embedder",
        "collection": "tm",
        "provider": "mock",
        "llm_model": None,
        "llm_base_url": None,
        "prompt_version": "1.0",
        "options": {"target_lang": None, "hybrid": False, "rrf_k": 60},
        "gold_file": "gold.jsonl",
        "cross_language": False,
        "n_units": 3,
        "n_gold": 2,
        "k_values": [1, 3],
        "recall_at_k": {"1": 0.75, "3": 1.0},
        "mrr": 0.9,
        "qa_pass_rate": 0.5,
        "qa_by_check": {"placeholder_preservation": 1.0, "number_preservation": 0.5},
        "qa_failures": [],
        "bad_json_count": 0,
        "wall_time_seconds": 1.25,
        "items": [
            {
                "query": "a boss is near",
                "expected_id": "t1",
                "rank": 1,
                "top_match_id": "t1",
                "top_match_score": 0.99,
                "translation": "<b>hax</b> not escaped?",
                "qa_passed": False,
                "failed_checks": ["number_preservation"],
                "bad_json": False,
            },
            {
                "query": "brand new playthrough",
                "expected_id": "t2",
                "rank": 2,
                "top_match_id": "t2",
                "top_match_score": 0.9,
                "translation": "新游戏",
                "qa_passed": True,
                "failed_checks": [],
                "bad_json": False,
            },
        ],
    }
    model = dict(retrieval)
    model.update(
        {
            "config": "baseline + model",
            "kind": "model",
            "provider": "ollama",
            "llm_model": "fixture-model:1b",
            "prompt_version": "2.0",
            "qa_pass_rate": 1.0,
            "qa_by_check": {"placeholder_preservation": 1.0, "number_preservation": 1.0},
            "bad_json_count": 0,
            "wall_time_seconds": 3.5,
        }
    )
    (results_dir / "eval.json").write_text(json.dumps(retrieval, ensure_ascii=False), encoding="utf-8")
    (results_dir / "eval_model.json").write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def report_inputs(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "tm.tmx").write_text(TAG_TMX, encoding="utf-8")
    results_dir = tmp_path / "results"
    _write_fixture_results(results_dir)
    experiments = tmp_path / "EXPERIMENTS.md"
    experiments.write_text(EXPERIMENTS_FIXTURE, encoding="utf-8")
    out_dir = tmp_path / "docs"
    return data_dir, results_dir, experiments, out_dir


def _section(page: str, title: str) -> str:
    start = page.index(title)
    return page[start:page.index("</section>", start)]


def test_report_contains_numbers_from_fixture_results(report_inputs):
    data_dir, results_dir, experiments, out_dir = report_inputs
    index_path, svg_path = build_report(
        results_dir=results_dir,
        data_dir=data_dir,
        out_dir=out_dir,
        experiments_path=experiments,
    )
    page = index_path.read_text(encoding="utf-8")
    # fixture values as one-decimal percentages, computed with the same pct() as the page
    assert pct(0.75) in page
    assert pct(1.0) in page
    assert pct(0.9) in page
    assert pct(0.5) in page
    assert "0.7500" not in page
    assert "fixture-model:1b" in page
    assert svg_path.exists()
    assert "<svg" in svg_path.read_text(encoding="utf-8")


def test_report_has_no_external_resource_loads(report_inputs):
    data_dir, results_dir, experiments, out_dir = report_inputs
    index_path, _ = build_report(
        results_dir=results_dir,
        data_dir=data_dir,
        out_dir=out_dir,
        experiments_path=experiments,
    )
    page = index_path.read_text(encoding="utf-8")
    assert "http://" not in page
    assert "https://" not in page
    assert "<script" not in page
    assert "<link" not in page
    assert "@import" not in page


def test_report_escapes_html_in_segments_and_outputs(report_inputs):
    data_dir, results_dir, experiments, out_dir = report_inputs
    index_path, _ = build_report(
        results_dir=results_dir,
        data_dir=data_dir,
        out_dir=out_dir,
        experiments_path=experiments,
    )
    page = index_path.read_text(encoding="utf-8")
    assert "&lt;b&gt;Warning:&lt;/b&gt; a boss is near" in page
    assert "&lt;b&gt;hax&lt;/b&gt; not escaped?" in page
    assert "<b>hax</b>" not in page
    assert "<b>Warning:</b>" not in page


def test_report_renders_experiment_tables_and_qa_bars(report_inputs):
    data_dir, results_dir, experiments, out_dir = report_inputs
    index_path, _ = build_report(
        results_dir=results_dir,
        data_dir=data_dir,
        out_dir=out_dir,
        experiments_path=experiments,
    )
    page = index_path.read_text(encoding="utf-8")
    assert "baseline" in page
    assert _section(page, "What we tried").count("<table") == 1
    assert "bar-row" in page
    assert "placeholder_preservation" in page
    assert "number_preservation" in page
    assert "新遊戲" in page
    assert "เกมใหม่" in page


def test_report_shows_fixture_percentage_and_drops_repeated_k_tables(report_inputs, tmp_path):
    data_dir, results_dir, experiments, out_dir = report_inputs
    full_experiments = tmp_path / "EXPERIMENTS_FULL.md"
    full_experiments.write_text(EXPERIMENTS_FULL_FIXTURE, encoding="utf-8")
    index_path, _ = build_report(
        results_dir=results_dir,
        data_dir=data_dir,
        out_dir=out_dir,
        experiments_path=full_experiments,
    )
    page = index_path.read_text(encoding="utf-8")
    # the percentage computed from the fixture results (recall@1 0.75, mock QA 0.5)
    assert pct(0.75) in page
    assert pct(0.5) in page
    # only the summary table is rendered, not the repeated per-experiment k tables
    tried = _section(page, "What we tried")
    assert tried.count("<table") == 1
    assert "<th>k</th>" not in tried
    assert "0.7500" not in page
    assert "0.5000" not in page
    # the kept configuration's row is highlighted
    assert 'class="kept-row"' in page


def test_report_command_via_cli(report_inputs, capsys):
    data_dir, results_dir, experiments, out_dir = report_inputs
    rc = main(
        [
            "report",
            "--data-dir", str(data_dir),
            "--results-dir", str(results_dir),
            "--out-dir", str(out_dir),
            "--experiments", str(experiments),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "index.html" in out and "recall.svg" in out
    assert (out_dir / "index.html").exists()
    assert (out_dir / "recall.svg").exists()


def test_parse_markdown_tables_skips_separator_rows():
    tables = parse_markdown_tables(EXPERIMENTS_FIXTURE)
    assert tables == [[["config", "recall@1", "MRR", "kept"], ["baseline", "0.7500", "0.9000", "yes"]]]
