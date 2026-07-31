"""
Composite confidence scoring — an engineering heuristic, not a calibrated
probability that the answer is factually correct.
"""

import math
from dataclasses import dataclass

from app.core.config import settings
from app.retrieval.reranker import RerankedHit
from app.verification.citations import ClaimVerification, VerificationLabel


@dataclass
class ConfidenceBreakdown:
    overall_score: float
    label: str
    retrieval_confidence: float
    citation_coverage: float
    citation_validity: float
    evidence_agreement: float
    answer_completeness: float
    explanation: str


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _retrieval_confidence(cited_hits: list[RerankedHit]) -> float:
    if not cited_hits:
        return 0.0
    return sum(_sigmoid(h.reranker_score) for h in cited_hits) / len(cited_hits)


def _citation_coverage(total_claims: int, cited_claims: int) -> float:
    if total_claims == 0:
        return 0.0
    return cited_claims / total_claims


def _citation_validity(verifications: list[ClaimVerification]) -> float:
    verified = [v for v in verifications if v.label is not None]
    if not verified:
        return 0.0
    return sum(v.score for v in verified) / len(verified)


def _evidence_agreement(verifications: list[ClaimVerification]) -> float:
    verified = [v for v in verifications if v.label is not None]
    if not verified:
        return 0.0
    contradictions = sum(1 for v in verified if v.label == VerificationLabel.CONTRADICTS)
    return 1.0 - (contradictions / len(verified))


def _answer_completeness(insufficient_evidence: bool, claim_count: int) -> float:
    if insufficient_evidence or claim_count == 0:
        return 0.0
    if claim_count == 1:
        return 0.6
    return 1.0


def compute_confidence(
    cited_hits: list[RerankedHit], claims: list, verifications: list[ClaimVerification],
    insufficient_evidence: bool,
) -> ConfidenceBreakdown:
    cited_claim_count = sum(1 for c in claims if c.citation_numbers)

    retrieval = _retrieval_confidence(cited_hits)
    coverage = _citation_coverage(len(claims), cited_claim_count)
    validity = _citation_validity(verifications)
    agreement = _evidence_agreement(verifications)
    completeness = _answer_completeness(insufficient_evidence, len(claims))

    overall = (
        settings.confidence_weight_retrieval * retrieval
        + settings.confidence_weight_citation_validity * validity
        + settings.confidence_weight_citation_coverage * coverage
        + settings.confidence_weight_evidence_agreement * agreement
        + settings.confidence_weight_answer_completeness * completeness
    )
    overall_pct = round(overall * 100, 1)

    if insufficient_evidence:
        label = "Low"
    elif overall_pct >= 70:
        label = "High"
    elif overall_pct >= 40:
        label = "Moderate"
    else:
        label = "Low"

    explanation = (
        f"Retrieval relevance {retrieval:.0%}, {cited_claim_count}/{len(claims)} claims cited, "
        f"citation validity {validity:.0%}"
        + (", no contradictions found" if verifications and agreement == 1.0 else "")
        + "."
    )

    return ConfidenceBreakdown(
        overall_score=overall_pct, label=label, retrieval_confidence=round(retrieval, 3),
        citation_coverage=round(coverage, 3), citation_validity=round(validity, 3),
        evidence_agreement=round(agreement, 3), answer_completeness=round(completeness, 3),
        explanation=explanation,
    )
