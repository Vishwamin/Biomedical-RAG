"""
Shared RAG pipeline execution.

Extracted out of the /query route so both POST /api/v1/query and
POST /api/v1/chats/{id}/messages call exactly the same retrieval ->
rerank -> generate -> verify -> score sequence. This exists for the same
reason services/pipeline.py's mode-parameterized retrieval exists: two
call sites independently reimplementing "the same logic" is exactly how
the Phase 5 citation-parsing bug happened. There is now one function that
runs a question through the full pipeline and returns a QueryResponse;
every caller (both routes) is a thin wrapper around it.
"""

import json
import time
import uuid

from sqlalchemy.orm import Session

from app.confidence.scorer import compute_confidence
from app.core.config import settings
from app.core.exceptions import GenerationError, RetrievalError
from app.core.logging import get_logger
from app.generation.generator import generate_grounded_answer
from app.models.database import ClaimRecord, QueryHistoryRecord
from app.models.schemas import (
    ClaimSchema, ConfidenceBreakdownSchema, DenseRetrievalResult, FusedRetrievalResult, GenerationCitation,
    QueryResponse, RerankedResult, RetrievalDebugResponse, SparseRetrievalResult,
)
from app.retrieval import dense
from app.retrieval.reranker import rerank
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.sparse import bm25_store
from app.verification.citations import verify_claims
from app.verification.claims import extract_claims

logger = get_logger(__name__)


def execute_rag_query(
    question: str, db: Session, top_k: int | None = None, include_retrieval_debug: bool = False,
) -> QueryResponse:
    query_id = f"query_{uuid.uuid4().hex[:12]}"

    if not bm25_store.is_built:
        bm25_store.refresh(db)

    timings: dict[str, float] = {}
    t_start = time.perf_counter()

    t0 = time.perf_counter()
    try:
        dense_hits = dense.search(question, settings.dense_top_k)
    except Exception as exc:
        raise RetrievalError(f"Dense retrieval failed: {exc}") from exc
    timings["dense_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    sparse_hits = bm25_store.search(question, settings.sparse_top_k)
    timings["sparse_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    fused_hits = reciprocal_rank_fusion(dense_hits, sparse_hits)
    timings["rrf_ms"] = (time.perf_counter() - t0) * 1000

    candidate_hits = fused_hits[: settings.rerank_candidate_k]
    resolved_top_k = top_k or settings.rerank_top_k

    t0 = time.perf_counter()
    try:
        reranked_hits = rerank(question, candidate_hits, top_k=resolved_top_k)
    except Exception as exc:
        raise RetrievalError(f"Reranking failed: {exc}") from exc
    timings["rerank_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    try:
        generated = generate_grounded_answer(question, reranked_hits)
    except GenerationError:
        raise
    except Exception as exc:
        raise GenerationError(f"Answer generation failed: {exc}") from exc
    timings["generation_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    evidence_by_number = {i + 1: hit.text for i, hit in enumerate(reranked_hits)}
    extracted_claims = extract_claims(generated.answer_text)
    try:
        verifications = verify_claims(extracted_claims, evidence_by_number)
    except Exception as exc:
        logger.error("claim_verification_batch_failed", extra={"event_data": {"error": str(exc)}})
        verifications = []
    timings["verification_ms"] = (time.perf_counter() - t0) * 1000

    verification_by_claim_id = {v.claim_id: v for v in verifications}
    claims_out = [
        ClaimSchema(
            claim_id=c.claim_id, claim_text=c.claim_text, citation_numbers=c.citation_numbers,
            verification_label=(verification_by_claim_id[c.claim_id].label if c.claim_id in verification_by_claim_id else None),
            verification_score=(verification_by_claim_id[c.claim_id].score if c.claim_id in verification_by_claim_id else None),
            verification_explanation=(
                verification_by_claim_id[c.claim_id].explanation if c.claim_id in verification_by_claim_id else None
            ),
        )
        for c in extracted_claims
    ]

    cited_hits = [reranked_hits[n - 1] for n in generated.cited_numbers if 0 < n <= len(reranked_hits)]
    confidence = compute_confidence(
        cited_hits=cited_hits, claims=extracted_claims, verifications=verifications,
        insufficient_evidence=generated.insufficient_evidence,
    )

    timings["total_ms"] = (time.perf_counter() - t_start) * 1000

    citations = [
        GenerationCitation(
            citation_number=i + 1, chunk_id=hit.chunk_id, document_id=hit.document_id,
            source_filename=hit.source_filename, document_title=hit.document_title,
            page_number=hit.page_number, section_heading=hit.section_heading, text_snippet=hit.text[:280],
        )
        for i, hit in enumerate(reranked_hits)
        if (i + 1) in generated.cited_numbers
    ]

    sources = sorted({hit.source_filename for hit in reranked_hits})

    retrieval_debug = None
    if include_retrieval_debug:
        retrieval_debug = RetrievalDebugResponse(
            question=question,
            dense_results=[DenseRetrievalResult(**vars(h)) for h in dense_hits],
            sparse_results=[SparseRetrievalResult(**vars(h)) for h in sparse_hits],
            fused_results=[FusedRetrievalResult(**vars(h)) for h in fused_hits],
            reranked_results=[RerankedResult(**vars(h)) for h in reranked_hits],
            dense_latency_ms=timings["dense_ms"], sparse_latency_ms=timings["sparse_ms"],
            rrf_latency_ms=timings["rrf_ms"], rerank_latency_ms=timings["rerank_ms"],
        )

    db.add(
        QueryHistoryRecord(
            query_id=query_id, question=question, answer=generated.answer_text,
            confidence_score=confidence.overall_score, insufficient_evidence=generated.insufficient_evidence,
            dense_latency_ms=timings["dense_ms"], sparse_latency_ms=timings["sparse_ms"],
            rrf_latency_ms=timings["rrf_ms"], rerank_latency_ms=timings["rerank_ms"],
            generation_latency_ms=timings["generation_ms"], verification_latency_ms=timings["verification_ms"],
            total_latency_ms=timings["total_ms"],
        )
    )
    for c in claims_out:
        db.add(
            ClaimRecord(
                claim_id=c.claim_id, query_id=query_id, claim_text=c.claim_text,
                citation_numbers=json.dumps(c.citation_numbers),
                verification_label=c.verification_label.value if c.verification_label else None,
                verification_score=c.verification_score, verification_explanation=c.verification_explanation,
            )
        )
    db.commit()

    logger.info(
        "query_completed",
        extra={"event_data": {"query_id": query_id, **timings, "insufficient_evidence": generated.insufficient_evidence,
                               "citation_count": len(citations), "claim_count": len(claims_out),
                               "confidence_score": confidence.overall_score, "confidence_label": confidence.label}},
    )

    return QueryResponse(
        question=question, answer=generated.answer_text,
        insufficient_evidence=generated.insufficient_evidence, citations=citations, sources=sources,
        claims=claims_out, confidence=confidence.overall_score, confidence_label=confidence.label,
        confidence_breakdown=ConfidenceBreakdownSchema(**vars(confidence)),
        retrieval_debug=retrieval_debug, processing_latency_ms=timings,
    )
