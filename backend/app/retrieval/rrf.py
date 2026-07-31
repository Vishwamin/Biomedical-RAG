"""
Reciprocal Rank Fusion (RRF) — implemented by hand, not via a library.
"""

from dataclasses import dataclass

from app.core.config import settings
from app.retrieval.dense import DenseHit
from app.retrieval.sparse import SparseHit


@dataclass
class FusedHit:
    chunk_id: str
    document_id: str
    text: str
    dense_rank: int | None
    dense_score: float | None
    sparse_rank: int | None
    bm25_score: float | None
    rrf_score: float
    fused_rank: int
    page_number: int | None
    section_heading: str | None
    document_title: str | None
    source_filename: str


def reciprocal_rank_fusion(
    dense_hits: list[DenseHit], sparse_hits: list[SparseHit],
    k: int | None = None, dense_weight: float | None = None, sparse_weight: float | None = None,
) -> list[FusedHit]:
    k = k if k is not None else settings.rrf_k
    dense_weight = dense_weight if dense_weight is not None else settings.dense_weight
    sparse_weight = sparse_weight if sparse_weight is not None else settings.sparse_weight

    dense_by_id = {h.chunk_id: h for h in dense_hits}
    sparse_by_id = {h.chunk_id: h for h in sparse_hits}
    all_chunk_ids = dense_by_id.keys() | sparse_by_id.keys()

    scored: list[FusedHit] = []
    for chunk_id in all_chunk_ids:
        dense_hit = dense_by_id.get(chunk_id)
        sparse_hit = sparse_by_id.get(chunk_id)
        meta = dense_hit or sparse_hit

        score = 0.0
        if dense_hit is not None:
            score += dense_weight * (1.0 / (k + dense_hit.dense_rank))
        if sparse_hit is not None:
            score += sparse_weight * (1.0 / (k + sparse_hit.sparse_rank))

        scored.append(
            FusedHit(
                chunk_id=chunk_id, document_id=meta.document_id, text=meta.text,
                dense_rank=dense_hit.dense_rank if dense_hit else None,
                dense_score=dense_hit.dense_score if dense_hit else None,
                sparse_rank=sparse_hit.sparse_rank if sparse_hit else None,
                bm25_score=sparse_hit.bm25_score if sparse_hit else None,
                rrf_score=score, fused_rank=0, page_number=meta.page_number,
                section_heading=meta.section_heading, document_title=meta.document_title,
                source_filename=meta.source_filename,
            )
        )

    scored.sort(key=lambda h: h.rrf_score, reverse=True)
    for rank, hit in enumerate(scored, start=1):
        hit.fused_rank = rank

    return scored
