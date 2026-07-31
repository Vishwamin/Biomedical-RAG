"""
Cross-encoder reranking. Model: cross-encoder/ms-marco-MiniLM-L-6-v2.
"""

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.retrieval.rrf import FusedHit

logger = get_logger(__name__)


@lru_cache
def _get_model():
    from sentence_transformers import CrossEncoder

    logger.info(
        "loading_reranker_model",
        extra={"event_data": {"model": settings.reranker_model, "device": settings.reranker_device}},
    )
    return CrossEncoder(settings.reranker_model, device=settings.reranker_device)


def score_pairs(query: str, passages: list[str]) -> list[float]:
    if not passages:
        return []
    model = _get_model()
    pairs = [[query, p] for p in passages]
    scores = model.predict(pairs)
    return [float(s) for s in scores]


@dataclass
class RerankedHit:
    chunk_id: str
    document_id: str
    text: str
    dense_rank: int | None
    dense_score: float | None
    sparse_rank: int | None
    bm25_score: float | None
    rrf_rank: int | None
    rrf_score: float | None
    reranker_score: float
    final_rank: int
    page_number: int | None
    section_heading: str | None
    document_title: str | None
    source_filename: str


def rerank(query: str, fused_hits: list[FusedHit], top_k: int, score_fn=None) -> list[RerankedHit]:
    """`fused_hits` should already be limited to the top RERANK_CANDIDATE_K."""
    score_fn = score_fn or score_pairs

    candidates = fused_hits
    if not candidates:
        return []

    passages = [c.text for c in candidates]
    scores = score_fn(query, passages)

    scored_pairs = list(zip(candidates, scores))
    scored_pairs.sort(key=lambda pair: pair[1], reverse=True)
    top = scored_pairs[:top_k]

    results: list[RerankedHit] = []
    for rank, (hit, score) in enumerate(top, start=1):
        results.append(
            RerankedHit(
                chunk_id=hit.chunk_id, document_id=hit.document_id, text=hit.text,
                dense_rank=hit.dense_rank, dense_score=hit.dense_score, sparse_rank=hit.sparse_rank,
                bm25_score=hit.bm25_score, rrf_rank=hit.fused_rank, rrf_score=hit.rrf_score,
                reranker_score=float(score), final_rank=rank, page_number=hit.page_number,
                section_heading=hit.section_heading, document_title=hit.document_title,
                source_filename=hit.source_filename,
            )
        )
    return results
