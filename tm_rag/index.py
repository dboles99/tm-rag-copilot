"""Embed translation units with fastembed and store them in a local Qdrant.

The embedding model is a multilingual MiniLM served from the local fastembed
cache (HF_HUB_OFFLINE defaults to 1, so no network call is made when the model
is cached). Vectors live in a Qdrant local-mode directory (./.qdrant by
default), so the whole demo runs offline.
"""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

from .retrieve import DEFAULT_RRF_K, bm25_scores, build_bm25, rank_by_score, rrf_fuse
from .tmx import TranslationUnit, parse_tmx

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
DEFAULT_QDRANT = Path(".qdrant")

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION = "tm"


@dataclass
class Match:
    unit: TranslationUnit
    score: float


_model = None


def get_model():
    """Load the embedding model once per process."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    vectors = list(model.embed(list(texts)))
    return [v.tolist() for v in vectors]


@contextmanager
def _client(qdrant_path: str | Path):
    """Open a local Qdrant client and always close it.

    Closing in a finally block (instead of relying on __del__ at interpreter
    shutdown) keeps qdrant-client's portalocker from printing "Exception
    ignored" noise when the process exits.
    """
    from qdrant_client import QdrantClient

    client = QdrantClient(path=str(Path(qdrant_path)))
    try:
        yield client
    finally:
        client.close()


def _payload_filter(target_lang: str | None):
    if not target_lang:
        return None
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    return Filter(must=[FieldCondition(key="tgt_lang", match=MatchValue(value=target_lang))])


def _unit_from_payload(payload: dict) -> TranslationUnit:
    return TranslationUnit(
        source=payload["source"],
        target=payload["target"],
        src_lang=payload["src_lang"],
        tgt_lang=payload["tgt_lang"],
        id=payload["id"],
    )


def index_exists(qdrant_path: str | Path = DEFAULT_QDRANT) -> bool:
    with _client(qdrant_path) as client:
        return client.collection_exists(COLLECTION)


def build_index(
    tmx_path: str | Path = DATA_DIR / "tm.tmx",
    qdrant_path: str | Path = DEFAULT_QDRANT,
) -> int:
    """Embed every TM unit source and (re)build the Qdrant collection.

    Returns the number of units indexed.
    """
    from qdrant_client.models import Distance, PointStruct, VectorParams

    units = parse_tmx(tmx_path)
    if not units:
        raise ValueError(f"no translation units found in {tmx_path}")
    vectors = embed_texts([u.source for u in units])
    with _client(qdrant_path) as client:
        if client.collection_exists(COLLECTION):
            client.delete_collection(COLLECTION)
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
        )
        points = [
            PointStruct(
                id=i,
                vector=vectors[i],
                payload={
                    "id": unit.id,
                    "source": unit.source,
                    "target": unit.target,
                    "src_lang": unit.src_lang,
                    "tgt_lang": unit.tgt_lang,
                },
            )
            for i, unit in enumerate(units)
        ]
        client.upsert(collection_name=COLLECTION, points=points)
        return len(units)


def search(
    text: str,
    k: int = 5,
    qdrant_path: str | Path = DEFAULT_QDRANT,
    target_lang: str | None = None,
    hybrid: bool = False,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[Match]:
    """Return the k closest TM units for a query text, best first.

    target_lang restricts matches to one target language via a payload filter,
    which stops the variants of one source segment (zh-CN, zh-TW, th) from
    crowding the top-k. hybrid fuses the vector ranking with a pure-Python
    BM25 over the same (filtered) source segments using reciprocal rank
    fusion; the returned scores are then normalised RRF scores in (0, 1].
    """
    vector = embed_texts([text])[0]
    query_filter = _payload_filter(target_lang)
    with _client(qdrant_path) as client:
        if not client.collection_exists(COLLECTION):
            return []
        total = client.count(collection_name=COLLECTION, count_filter=query_filter, exact=True).count
        limit = max(1, min(total if hybrid else k, 1000))
        response = client.query_points(
            collection_name=COLLECTION,
            query=vector,
            limit=limit,
            query_filter=query_filter,
        )
        payloads: dict[str, dict] = {}
        vector_hits: list[tuple[str, float]] = []
        for point in response.points:
            payload = point.payload or {}
            payloads[payload["id"]] = payload
            vector_hits.append((payload["id"], point.score))
        if not hybrid:
            return [
                Match(unit=_unit_from_payload(payloads[item_id]), score=score)
                for item_id, score in vector_hits[:k]
            ]
        ids: list[str] = []
        sources: list[str] = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=COLLECTION,
                scroll_filter=query_filter,
                limit=256,
                with_vectors=False,
                offset=offset,
            )
            for point in points:
                payload = point.payload or {}
                ids.append(payload["id"])
                sources.append(payload["source"])
                payloads.setdefault(payload["id"], payload)
            if offset is None:
                break
        index = build_bm25(sources)
        bm25_ranking = rank_by_score(ids, bm25_scores(index, text))
        vector_ranking = [item_id for item_id, _ in vector_hits]
        fused = rrf_fuse([vector_ranking, bm25_ranking], k=rrf_k)
        return [
            Match(unit=_unit_from_payload(payloads[item_id]), score=score)
            for item_id, score in fused[:k]
            if item_id in payloads
        ]


def ensure_index(
    tmx_path: str | Path = DATA_DIR / "tm.tmx",
    qdrant_path: str | Path = DEFAULT_QDRANT,
) -> None:
    """Build the index on first use if the collection is missing."""
    if not index_exists(qdrant_path):
        build_index(tmx_path, qdrant_path)
