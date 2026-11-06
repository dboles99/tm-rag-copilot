"""Measured evaluation: retrieval recall@k, MRR and QA pass rate on a gold set.

The gold set (data/gold.jsonl) holds paraphrased queries, each naming the
expected TM unit id. Retrieval is measured against that id; QA is measured by
running the full pipeline on the expected unit's source segment and checking
the output with the deterministic QA rules. results/eval.json is the default
output; --results writes elsewhere.

Retrieval options: target_lang filters matches to one target language and
hybrid fuses the vector search with a BM25 ranking (RRF). --cross-lang switches
to data/gold_zh.jsonl, Chinese queries searched against the English sources.

The provider can be a real model ("ollama"): the prompt then asks for a JSON
reply (version 2.0), bad JSON is retried once and counted as a failure, and
the wall time of the run is recorded.
"""

import json
import time
from pathlib import Path

from .index import (
    COLLECTION,
    DATA_DIR,
    DEFAULT_QDRANT,
    MODEL_NAME,
    RESULTS_DIR,
    ensure_index,
    search,
)
from .llm import GenContext, get_provider
from .prompts import PROMPT_VERSION, PROMPT_VERSION_JSON, build_prompt, build_prompt_json
from .qa import all_passed, run_qa
from .tbx import parse_tbx
from .tmx import parse_tmx

CROSS_LANG_GOLD = "gold_zh.jsonl"


def load_gold(path: str | Path) -> list[dict]:
    items = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _config_label(target_lang: str | None, hybrid: bool, cross_lang: bool) -> str:
    parts = []
    if target_lang:
        parts.append(f"target-lang {target_lang}")
    if hybrid:
        parts.append("hybrid RRF+BM25")
    if cross_lang:
        parts.append("zh queries")
    return " + ".join(parts) if parts else "baseline"


def run_eval(
    data_dir: str | Path = DATA_DIR,
    qdrant_path: str | Path = DEFAULT_QDRANT,
    results_path: str | Path | None = None,
    k_values=(1, 3, 5, 10),
    provider_name: str = "mock",
    target_lang: str | None = None,
    hybrid: bool = False,
    cross_lang: bool = False,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    timeout: float = 120.0,
) -> dict:
    data_dir = Path(data_dir)
    tmx_path = data_dir / "tm.tmx"
    tbx_path = data_dir / "terms.tbx"
    gold_path = data_dir / (CROSS_LANG_GOLD if cross_lang else "gold.jsonl")

    units = parse_tmx(tmx_path)
    by_id = {u.id: u for u in units}
    terms = parse_tbx(tbx_path)
    gold = load_gold(gold_path)
    if not gold:
        raise ValueError(f"no gold queries found in {gold_path}")

    ensure_index(tmx_path, qdrant_path)

    ks = sorted({int(k) for k in k_values})
    max_k = max(ks)
    real_model = provider_name != "mock"
    provider = get_provider(
        provider_name,
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout=timeout,
    )
    prompt_version = PROMPT_VERSION_JSON if real_model else PROMPT_VERSION
    llm_model = getattr(provider, "model", None)
    llm_base_url = getattr(provider, "base_url", None)

    hits = {k: 0 for k in ks}
    rr_sum = 0.0
    qa_passed = 0
    qa_failures = []
    check_totals: dict[str, int] = {}
    check_passed: dict[str, int] = {}
    bad_json_count = 0
    items = []

    start = time.perf_counter()
    for item in gold:
        query = item["query"]
        expected = item["expected_id"]
        max_chars = item.get("max_chars")
        matches = search(
            query,
            k=max_k,
            qdrant_path=qdrant_path,
            target_lang=target_lang,
            hybrid=hybrid,
        )
        ids = [m.unit.id for m in matches]
        rank = ids.index(expected) + 1 if expected in ids else None
        for k in ks:
            if rank is not None and rank <= k:
                hits[k] += 1
        if rank is not None:
            rr_sum += 1.0 / rank

        unit = by_id.get(expected)
        source = unit.source if unit is not None else query
        context = GenContext(source=source, matches=matches, terms=terms, max_chars=max_chars)
        bad_json = False
        if real_model:
            prompt = build_prompt_json(source, matches, terms, max_chars)
            translation, gen_meta = provider.generate_translation(prompt, context)
            bad_json = gen_meta.get("bad_json", False)
        else:
            prompt = build_prompt(source, matches, terms, max_chars)
            translation = provider.generate(prompt, context)
        findings = run_qa(source, translation, terms, max_chars)
        passed = all_passed(findings) and not bad_json
        for finding in findings:
            check_totals[finding.check] = check_totals.get(finding.check, 0) + 1
            if finding.passed:
                check_passed[finding.check] = check_passed.get(finding.check, 0) + 1
        if passed:
            qa_passed += 1
        else:
            qa_failures.append(
                {
                    "query": query,
                    "expected_id": expected,
                    "failed_checks": [f.check for f in findings if not f.passed]
                    + (["json_output"] if bad_json else []),
                }
            )
        if bad_json:
            bad_json_count += 1
        items.append(
            {
                "query": query,
                "expected_id": expected,
                "rank": rank,
                "top_match_id": matches[0].unit.id if matches else None,
                "top_match_score": round(matches[0].score, 4) if matches else None,
                "translation": translation,
                "qa_passed": passed,
                "failed_checks": [f.check for f in findings if not f.passed]
                + (["json_output"] if bad_json else []),
                "bad_json": bad_json,
            }
        )
    wall_time = time.perf_counter() - start

    n = len(gold)
    result = {
        "config": _config_label(target_lang, hybrid, cross_lang),
        "kind": "model" if real_model else "retrieval",
        "model": MODEL_NAME,
        "collection": COLLECTION,
        "provider": provider.name,
        "llm_model": llm_model,
        "llm_base_url": llm_base_url,
        "prompt_version": prompt_version,
        "options": {"target_lang": target_lang, "hybrid": hybrid, "rrf_k": 60},
        "gold_file": gold_path.name,
        "cross_language": cross_lang,
        "n_units": len(units),
        "n_gold": n,
        "k_values": ks,
        "recall_at_k": {str(k): round(hits[k] / n, 4) for k in ks},
        "mrr": round(rr_sum / n, 4),
        "qa_pass_rate": round(qa_passed / n, 4),
        "qa_by_check": {
            check: round(check_passed.get(check, 0) / total, 4)
            for check, total in sorted(check_totals.items())
        },
        "qa_failures": qa_failures,
        "bad_json_count": bad_json_count,
        "wall_time_seconds": round(wall_time, 2),
        "items": items,
    }

    out = Path(results_path) if results_path is not None else RESULTS_DIR / "eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
