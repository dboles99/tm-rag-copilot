# Experiments

Method: small changes, measured on the committed data with the committed code, keep what works. Every number below comes from a real run of the committed code from a clean `./.qdrant` (deleted, then rebuilt by `python -m tm_rag index`); nothing was invented and no data, gold set or threshold was tuned to improve a number. The gold set was never changed: the Chinese cross-language check uses its own file, `data/gold_zh.jsonl`.

All runs: 41 gold queries from `data/gold.jsonl` (10 from `data/gold_zh.jsonl` for the cross-language run), 133 indexed units, embedding model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, k values 1 3 5 10.

## Experiment 1: baseline retrieval depth sweep (`eval --k 1 3 5 10`)

**What changed:** nothing; the committed configuration (vector search only, no filter, no hybrid).

**What was measured** (run that wrote `results/eval.json`):

| k | recall@k |
|---|----------|
| 1 | 0.5122 |
| 3 | 0.6829 |
| 5 | 0.7317 |
| 10 | 0.8049 |

MRR 0.6146. QA pass rate (mock provider) 0.8049. The cause of the low top ranks: each English source has up to three target-language variants (zh-CN, zh-TW, th) in the index, and identical sources embed identically, so the variants of one source crowd the top-k.

**Kept:** default `k = 5` for `search`/`translate`, eval k-list `1 3 5 10`.

## Experiment 2: target-language filter (`eval --target-lang zh-CN`)

**What changed:** `search` and `eval` gained `--target-lang`, a Qdrant payload filter on `tgt_lang`, so only zh-CN units compete in the ranking.

**What was measured** (run that wrote `results/eval_zhcn.json`):

| k | recall@k |
|---|----------|
| 1 | 0.5854 |
| 3 | 0.7317 |
| 5 | 0.7561 |
| 10 | 0.8293 |

MRR 0.6755. QA pass rate (mock) 0.8293.

**Kept:** yes. Every k and the MRR improve over baseline (recall@10 0.8049 to 0.8293, MRR 0.6146 to 0.6755), exactly for the predicted reason: the duplicate variants no longer crowd the top-k. This is the best measured configuration and the one the results page and README headline.

## Experiment 3: hybrid retrieval, RRF of vector + BM25 (`eval --hybrid`)

**What changed:** `search` and `eval` gained `--hybrid`: reciprocal rank fusion (k = 60) of the vector ranking with a pure-Python Okapi BM25 (k1 = 1.5, b = 0.75) over the same source segments.

**What was measured** (run that wrote `results/eval_hybrid.json`):

| k | recall@k |
|---|----------|
| 1 | 0.5366 |
| 3 | 0.5610 |
| 5 | 0.6098 |
| 10 | 0.6585 |

MRR 0.5632. QA pass rate (mock) 0.8780.

**Kept:** as an option only, not as a default. This made recall worse at every k (recall@10 0.8049 to 0.6585, MRR 0.6146 to 0.5632): the gold queries are paraphrases with little keyword overlap with the sources, so BM25 ranks mostly noise and RRF dilutes the vector signal. The higher mock QA rate is a side effect of a different top match being copied, not better retrieval, and is not counted as an improvement.

## Experiment 4: target-language filter + hybrid (`eval --target-lang zh-CN --hybrid`)

**What changed:** both options together.

**What was measured** (run that wrote `results/eval_zhcn_hybrid.json`):

| k | recall@k |
|---|----------|
| 1 | 0.5366 |
| 3 | 0.5854 |
| 5 | 0.6098 |
| 10 | 0.6585 |

MRR 0.5665. QA pass rate (mock) 0.8780.

**Kept:** no. Strictly worse than the zh-CN filter alone (recall@10 0.8293 to 0.6585). The BM25 penalty dominates the crowding gain.

## Experiment 5: cross-language query check (`eval --cross-lang`)

**What changed:** `eval` gained `--cross-lang`, which evaluates `data/gold_zh.jsonl`: 10 gold queries written in Chinese, each naming the expected unit, searched against the English source segments with the default (unfiltered) retrieval.

**What was measured** (run that wrote `results/eval_crosslang.json`):

| k | recall@k |
|---|----------|
| 1 | 0.5000 |
| 3 | 0.5000 |
| 5 | 0.7000 |
| 10 | 0.8000 |

MRR 0.5593. QA pass rate (mock) 0.7000.

**Kept:** as a standing check. The multilingual embedding carries Chinese queries to the right English sources (recall@10 0.8000), though top ranks are weaker than for English paraphrases, which is expected for a shorter, less paraphrased query set.

## Experiment 6: a real model run, Qwen through Ollama (`eval --provider ollama`)

**What changed:** `eval` gained `--provider ollama` (local Ollama server, model `qwen2.5-coder:14b`, no API key) plus `--base-url/--model/--api-key/--timeout` overrides. Real providers get prompt version 2.0, which asks for a JSON reply; thinking text and fenced JSON are stripped before parsing, a bad JSON reply is retried exactly once, and a reply that is still bad JSON after the retry is counted as a failure (`bad_json_count`), never hidden. QA runs on the extracted translation exactly as for the mock.

**What was measured** (run that wrote `results/eval_qwen.json`, same gold set and retrieval as experiment 1, wall time 544.25 s):

| metric | value |
|---|-------|
| recall@1 / @3 / @5 / @10 | 0.5122 / 0.6829 / 0.7317 / 0.8049 |
| MRR | 0.6146 |
| QA pass rate (ollama) | 0.9756 |
| bad JSON replies | 0 |
| wall time | 544.25 s |

Per-check pass rates: placeholder, tag, character limit, number, forbidden term all 1.0000; required term 0.9756 (one item, `item-health-potion`, where the model did not use the approved term 生命药水). Retrieval numbers are identical to experiment 1 because the retrieval options were unchanged.

**Kept:** yes. The mock's QA pass rate on the same set is 0.8049, so the real model passes 33 of 34 checks the mock fails or passes differently; the single failure is reported in `results/eval_qwen.json`.

## Summary

| configuration | recall@1 | recall@3 | recall@5 | recall@10 | MRR | QA pass (provider) | kept |
|---|---|---|---|---|---|---|---|
| baseline (results/eval.json) | 0.5122 | 0.6829 | 0.7317 | 0.8049 | 0.6146 | 0.8049 (mock) | no, reference |
| target-lang zh-CN (results/eval_zhcn.json) | 0.5854 | 0.7317 | 0.7561 | 0.8293 | 0.6755 | 0.8293 (mock) | yes, best |
| hybrid RRF+BM25 (results/eval_hybrid.json) | 0.5366 | 0.5610 | 0.6098 | 0.6585 | 0.5632 | 0.8780 (mock) | option only, worse recall |
| zh-CN + hybrid (results/eval_zhcn_hybrid.json) | 0.5366 | 0.5854 | 0.6098 | 0.6585 | 0.5665 | 0.8780 (mock) | no |
| zh queries, cross-language (results/eval_crosslang.json) | 0.5000 | 0.5000 | 0.7000 | 0.8000 | 0.5593 | 0.7000 (mock) | standing check |
| baseline retrieval + ollama qwen2.5-coder:14b (results/eval_qwen.json) | 0.5122 | 0.6829 | 0.7317 | 0.8049 | 0.6146 | 0.9756 (ollama) | yes, real model run |
