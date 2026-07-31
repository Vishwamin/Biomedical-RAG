"""
Shared retrieval pipeline, parameterized by retrieval mode. Used by the
Phase 6 evaluation ablation study.
"""

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.core.config import settings
from app.retrieval import dense
from app.retrieval.dense import DenseHit
from app.retrieval.reranker import RerankedHit
from app.retrieval.reranker import rerank as cross_encoder_rerank
from app.retrieval.rrf import FusedHit, reciprocal_rank_fusion
from app.retrieval.sparse import SparseHit, bm25_store


class RetrievalMode(str, Enum):
    DENSE_ONLY = "dense_only"
    SPARSE_ONLY = "sparse_only"
    HYBRID_RRF = "hybrid_rrf"
    HYBRID_RRF_RERANK = "hybrid_rrf_rerank"


@dataclass
class PipelineResult:
    hits: list[RerankedHit]
    dense_hits: list[DenseHit]
    sparse_hits: list[SparseHit]
    fused_hits: list[FusedHit]


def _wrap_dense_hit(hit: DenseHit, rank: int) -> RerankedHit:
    return RerankedHit(
        chunk_id=hit.chunk_id, document_id=hit.document_id, text=hit.text, dense_rank=hit.dense_rank,
        dense_score=hit.dense_score, sparse_rank=None, bm25_score=None, rrf_rank=None, rrf_score=None,
        reranker_score=hit.dense_score, final_rank=rank, page_number=hit.page_number,
        section_heading=hit.section_heading, document_title=hit.document_title, source_filename=hit.source_filename,
    )


def _wrap_sparse_hit(hit: SparseHit, rank: int) -> RerankedHit:
    return RerankedHit(
        chunk_id=hit.chunk_id, document_id=hit.document_id, text=hit.text, dense_rank=None, dense_score=None,
        sparse_rank=hit.sparse_rank, bm25_score=hit.bm25_score, rrf_rank=None, rrf_score=None,
        reranker_score=hit.bm25_score, final_rank=rank, page_number=hit.page_number,
        section_heading=hit.section_heading, document_title=hit.document_title, source_filename=hit.source_filename,
    )


def _wrap_fused_hit(hit: FusedHit, rank: int) -> RerankedHit:
    return RerankedHit(
        chunk_id=hit.chunk_id, document_id=hit.document_id, text=hit.text, dense_rank=hit.dense_rank,
        dense_score=hit.dense_score, sparse_rank=hit.sparse_rank, bm25_score=hit.bm25_score,
        rrf_rank=hit.fused_rank, rrf_score=hit.rrf_score, reranker_score=hit.rrf_score, final_rank=rank,
        page_number=hit.page_number, section_heading=hit.section_heading, document_title=hit.document_title,
        source_filename=hit.source_filename,
    )


def run_retrieval(
    question: str, db: Session, mode: RetrievalMode = RetrievalMode.HYBRID_RRF_RERANK, top_k: int | None = None,
) -> PipelineResult:
    top_k = top_k if top_k is not None else settings.rerank_top_k

    if not bm25_store.is_built:
        bm25_store.refresh(db)

    dense_hits: list[DenseHit] = []
    sparse_hits: list[SparseHit] = []
    fused_hits: list[FusedHit] = []

    if mode in (RetrievalMode.DENSE_ONLY, RetrievalMode.HYBRID_RRF, RetrievalMode.HYBRID_RRF_RERANK):
        dense_hits = dense.search(question, settings.dense_top_k)
    if mode in (RetrievalMode.SPARSE_ONLY, RetrievalMode.HYBRID_RRF, RetrievalMode.HYBRID_RRF_RERANK):
        sparse_hits = bm25_store.search(question, settings.sparse_top_k)

    if mode == RetrievalMode.DENSE_ONLY:
        hits = [_wrap_dense_hit(h, i + 1) for i, h in enumerate(dense_hits[:top_k])]
    elif mode == RetrievalMode.SPARSE_ONLY:
        hits = [_wrap_sparse_hit(h, i + 1) for i, h in enumerate(sparse_hits[:top_k])]
    else:
        fused_hits = reciprocal_rank_fusion(dense_hits, sparse_hits)
        if mode == RetrievalMode.HYBRID_RRF:
            hits = [_wrap_fused_hit(h, i + 1) for i, h in enumerate(fused_hits[:top_k])]
        else:
            candidates = fused_hits[: settings.rerank_candidate_k]
            hits = cross_encoder_rerank(question, candidates, top_k=top_k)

    return PipelineResult(hits=hits, dense_hits=dense_hits, sparse_hits=sparse_hits, fused_hits=fused_hits)
