import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import settings
from app.core.exceptions import RetrievalError
from app.core.logging import get_logger
from app.models.schemas import (
    DenseRetrievalResult, FusedRetrievalResult, RetrievalDebugRequest, RetrievalDebugResponse, SparseRetrievalResult,
)
from app.retrieval import dense
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.sparse import bm25_store

router = APIRouter(prefix="/retrieve", tags=["retrieval"])
logger = get_logger(__name__)


@router.post("", response_model=RetrievalDebugResponse)
async def debug_retrieve(request: RetrievalDebugRequest, db: Session = Depends(get_db)):
    dense_top_k = request.dense_top_k or settings.dense_top_k
    sparse_top_k = request.sparse_top_k or settings.sparse_top_k

    if not bm25_store.is_built:
        bm25_store.refresh(db)

    t0 = time.perf_counter()
    try:
        dense_hits = dense.search(request.question, dense_top_k)
    except Exception as exc:
        raise RetrievalError(f"Dense retrieval failed: {exc}") from exc
    t1 = time.perf_counter()

    sparse_hits = bm25_store.search(request.question, sparse_top_k)
    t2 = time.perf_counter()

    fused_hits = reciprocal_rank_fusion(dense_hits, sparse_hits)
    t3 = time.perf_counter()

    return RetrievalDebugResponse(
        question=request.question,
        dense_results=[DenseRetrievalResult(**vars(h)) for h in dense_hits],
        sparse_results=[SparseRetrievalResult(**vars(h)) for h in sparse_hits],
        fused_results=[FusedRetrievalResult(**vars(h)) for h in fused_hits],
        reranked_results=None,
        dense_latency_ms=(t1 - t0) * 1000, sparse_latency_ms=(t2 - t1) * 1000, rrf_latency_ms=(t3 - t2) * 1000,
    )
