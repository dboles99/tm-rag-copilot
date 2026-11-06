"""The README and the generated results page must agree with results/*.json."""

import json

from tm_rag.index import RESULTS_DIR, ROOT
from tm_rag.report import pct


def _fmt(value) -> str:
    return f"{float(value):.4f}"


def _checked_values():
    checked = []
    for path in sorted(RESULTS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        values = list(data["recall_at_k"].values()) + [data["mrr"], data["qa_pass_rate"]]
        for value in values:
            checked.append((path.name, value))
    return checked


def test_readme_and_results_page_numbers_match_results_json():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    checked = _checked_values()
    assert checked
    for filename, value in checked:
        assert _fmt(value) in readme, f"{filename}: {_fmt(value)} missing from README.md"
        # the page shows the same numbers as one-decimal percentages
        assert pct(value) in page, f"{filename}: {pct(value)} missing from docs/index.html"


def test_readme_links_chart_and_results_page():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/recall.svg" in readme
    assert "docs/index.html" in readme
