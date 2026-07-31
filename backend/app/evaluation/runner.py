"""
Evaluation runner: runs the golden dataset through the pipeline for one
or more retrieval modes, computes and persists metrics.
"""

import json
import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.evaluation.dataset import EvaluationCase, load_dataset
from app.evaluation.metrics import (
    evaluate_refusal, judge_answer_quality, mean_reciprocal_rank, precision_at_k, recall_at_k,
)
from app.generation.generator import generate_grounded_answer
from app.models.database import EvaluationResultRecord, EvaluationRunRecord
from app.services.pipeline import RetrievalMode, run_retrieval
from app.verification.citations import VerificationLabel, verify_claims
from app.verification.claims import extract_claims

logger = get_logger(__name__)

_RETRIEVAL_K_FOR_METRICS = 5


@dataclass
class EvaluationRunSummary:
    run_id: str
    retrieval_mode: str
    case_count: int
    metrics: dict[str, float]


def _run_single_case(case: EvaluationCase, db: Session, mode: RetrievalMode) -> dict:
    result = run_retrieval(case.question, db, mode=mode, top_k=_RETRIEVAL_K_FOR_METRICS)
    retrieved_filenames = [h.source_filename for h in result.hits]
    expected = set(case.expected_source_filenames)

    generated = generate_grounded_answer(case.question, result.hits)
    extracted_claims = extract_claims(generated.answer_text)
    evidence_by_number = {i + 1: hit.text for i, hit in enumerate(result.hits)}
    try:
        verifications = verify_claims(extracted_claims, evidence_by_number)
    except Exception as exc:
        logger.error("eval_case_verification_failed", extra={"event_data": {"case_id": case.case_id, "error": str(exc)}})
        verifications = []

    refusal = evaluate_refusal(case.is_answerable, generated.insufficient_evidence)

    cited_claims = [c for c in extracted_claims if c.citation_numbers]
    citation_coverage = len(cited_claims) / len(extracted_claims) if extracted_claims else 0.0
    verified = [v for v in verifications if v.label is not None]
    citation_validity = (sum(v.score for v in verified) / len(verified)) if verified else 0.0
    unsupported_cited = sum(
        1 for v in verified if v.label in (VerificationLabel.DOES_NOT_SUPPORT, VerificationLabel.CONTRADICTS)
    )

    quality = None
    if case.is_answerable and not generated.insufficient_evidence:
        quality = judge_answer_quality(case.question, generated.answer_text, case.expected_answer_summary)

    return {
        "case_id": case.case_id,
        "precision_at_k": precision_at_k(retrieved_filenames, expected, _RETRIEVAL_K_FOR_METRICS),
        "recall_at_k": recall_at_k(retrieved_filenames, expected, _RETRIEVAL_K_FOR_METRICS),
        "mrr": mean_reciprocal_rank(retrieved_filenames, expected),
        "correct_refusal": refusal.correct_refusal, "false_refusal": refusal.false_refusal,
        "citation_coverage": citation_coverage, "citation_validity": citation_validity,
        "cited_claim_count": len(cited_claims), "unsupported_cited_count": unsupported_cited,
        "faithfulness": quality.faithfulness if quality else None,
        "relevance": quality.relevance if quality else None,
        "correctness": quality.correctness if quality else None,
    }


def _aggregate(case_results: list[dict]) -> dict[str, float]:
    def _mean(key: str) -> float:
        values = [r[key] for r in case_results if r[key] is not None]
        return round(sum(values) / len(values), 4) if values else 0.0

    refusal_applicable = [r for r in case_results if r["correct_refusal"] is not None]
    false_refusal_applicable = [r for r in case_results if r["false_refusal"] is not None]
    total_cited = sum(r["cited_claim_count"] for r in case_results)
    total_unsupported = sum(r["unsupported_cited_count"] for r in case_results)

    return {
        "precision_at_k": _mean("precision_at_k"), "recall_at_k": _mean("recall_at_k"), "mrr": _mean("mrr"),
        "citation_coverage": _mean("citation_coverage"), "citation_validity": _mean("citation_validity"),
        "faithfulness": _mean("faithfulness"), "relevance": _mean("relevance"), "correctness": _mean("correctness"),
        "correct_refusal_rate": (
            round(sum(1 for r in refusal_applicable if r["correct_refusal"]) / len(refusal_applicable), 4)
            if refusal_applicable else 0.0
        ),
        "false_refusal_rate": (
            round(sum(1 for r in false_refusal_applicable if r["false_refusal"]) / len(false_refusal_applicable), 4)
            if false_refusal_applicable else 0.0
        ),
        "hallucination_rate": round(total_unsupported / total_cited, 4) if total_cited else 0.0,
    }


def run_evaluation(db: Session, modes: list[RetrievalMode] | None = None, dataset_path=None) -> list[EvaluationRunSummary]:
    modes = modes or [RetrievalMode.HYBRID_RRF_RERANK]
    cases = load_dataset(dataset_path)
    if not cases:
        return []

    summaries: list[EvaluationRunSummary] = []

    for mode in modes:
        run_id = f"eval_{uuid.uuid4().hex[:12]}"
        t0 = time.perf_counter()

        case_results = [_run_single_case(case, db, mode) for case in cases]
        aggregated = _aggregate(case_results)

        db.add(
            EvaluationRunRecord(
                run_id=run_id, retrieval_mode=mode.value,
                config_snapshot=json.dumps({"k": _RETRIEVAL_K_FOR_METRICS, "case_count": len(cases)}),
            )
        )
        for metric_name, metric_value in aggregated.items():
            db.add(
                EvaluationResultRecord(
                    result_id=f"result_{uuid.uuid4().hex[:12]}", run_id=run_id,
                    metric_name=metric_name, metric_value=metric_value,
                )
            )
        db.commit()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "evaluation_run_completed",
            extra={"event_data": {"run_id": run_id, "retrieval_mode": mode.value, "case_count": len(cases),
                                   "elapsed_ms": elapsed_ms, **aggregated}},
        )

        summaries.append(
            EvaluationRunSummary(run_id=run_id, retrieval_mode=mode.value, case_count=len(cases), metrics=aggregated)
        )

    return summaries
