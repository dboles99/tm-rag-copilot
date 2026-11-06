"""Pure-Python BM25 and reciprocal rank fusion (RRF) for hybrid retrieval.

No ranking library is used: Okapi BM25 over the source segments and RRF over
the vector and BM25 rankings are computed here, so the behaviour is easy to
unit test and the demo stays dependency-light.
"""

import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"[a-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff]")

K1 = 1.5
B = 0.75
DEFAULT_RRF_K = 60


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric word tokens plus single CJK characters."""
    return TOKEN_RE.findall(text.lower())


def build_bm25(docs: list[str]) -> dict:
    """Build a BM25 index over tokenized documents."""
    tokenized = [tokenize(doc) for doc in docs]
    n = len(tokenized)
    avgdl = sum(len(toks) for toks in tokenized) / n if n else 0.0
    df: Counter = Counter()
    for toks in tokenized:
        df.update(set(toks))
    idf = {term: math.log(1.0 + (n - count + 0.5) / (count + 0.5)) for term, count in df.items()}
    return {"docs": tokenized, "avgdl": avgdl, "idf": idf, "n": n}


def bm25_scores(index: dict, query: str) -> list[float]:
    """BM25 score of every document for a query, in document order."""
    query_terms = tokenize(query)
    avgdl = index["avgdl"]
    scores = []
    for toks in index["docs"]:
        tf = Counter(toks)
        dl = len(toks)
        score = 0.0
        for term in query_terms:
            freq = tf.get(term, 0)
            if not freq:
                continue
            idf = index["idf"].get(term, 0.0)
            length_norm = 1.0 - B + B * dl / avgdl if avgdl else 1.0
            score += idf * (freq * (K1 + 1.0)) / (freq + K1 * length_norm)
        scores.append(score)
    return scores


def rank_by_score(ids: list[str], scores: list[float]) -> list[str]:
    """Ids ordered by descending score; ties broken by id for determinism."""
    order = sorted(range(len(ids)), key=lambda i: (-scores[i], ids[i]))
    return [ids[i] for i in order]


def rrf_fuse(rankings: list[list[str]], k: int = DEFAULT_RRF_K) -> list[tuple[str, float]]:
    """Fuse id rankings with reciprocal rank fusion.

    Returns (id, score) pairs sorted best first, with scores normalised so the
    best item gets 1.0; every score stays in (0, 1].
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    if not scores:
        return []
    top = max(scores.values())
    fused = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(item_id, value / top) for item_id, value in fused]
