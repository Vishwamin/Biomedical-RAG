from app.confidence.scorer import compute_confidence
from app.retrieval.reranker import RerankedHit
from app.verification.citations import ClaimVerification, VerificationLabel
from app.verification.claims import ExtractedClaim


def _hit(chunk_id="c1", reranker_score=2.0):
    return RerankedHit(
        chunk_id=chunk_id, document_id="doc1", text="some evidence text", dense_rank=1, dense_score=0.9,
        sparse_rank=1, bm25_score=5.0, rrf_rank=1, rrf_score=0.03, reranker_score=reranker_score, final_rank=1,
        page_number=1, section_heading="Results", document_title="Doc", source_filename="doc.pdf",
    )


def test_insufficient_evidence_forces_low_label_and_zero_completeness():
    breakdown = compute_confidence(cited_hits=[], claims=[], verifications=[], insufficient_evidence=True)
    assert breakdown.label == "Low"
    assert breakdown.answer_completeness == 0.0
    assert breakdown.overall_score == 0.0


def test_well_supported_answer_scores_high():
    hits = [_hit(reranker_score=5.0), _hit(chunk_id="c2", reranker_score=5.0)]
    claims = [
        ExtractedClaim(claim_id="claim_01", claim_text="Claim A", citation_numbers=[1]),
        ExtractedClaim(claim_id="claim_02", claim_text="Claim B", citation_numbers=[2]),
    ]
    verifications = [
        ClaimVerification("claim_01", "Claim A", [1], VerificationLabel.FULLY_SUPPORTS, 1.0, "matches"),
        ClaimVerification("claim_02", "Claim B", [2], VerificationLabel.FULLY_SUPPORTS, 1.0, "matches"),
    ]
    breakdown = compute_confidence(hits, claims, verifications, insufficient_evidence=False)
    assert breakdown.citation_coverage == 1.0
    assert breakdown.citation_validity == 1.0
    assert breakdown.evidence_agreement == 1.0
    assert breakdown.label == "High"
    assert breakdown.overall_score > 70


def test_unverified_claims_lower_coverage_and_validity():
    claims = [
        ExtractedClaim(claim_id="claim_01", claim_text="Claim A", citation_numbers=[1]),
        ExtractedClaim(claim_id="claim_02", claim_text="Claim B with no citation", citation_numbers=[]),
    ]
    verifications = [
        ClaimVerification("claim_01", "Claim A", [1], VerificationLabel.FULLY_SUPPORTS, 1.0, "matches"),
        ClaimVerification("claim_02", "Claim B with no citation", [], None, 0.0, "no citation"),
    ]
    breakdown = compute_confidence([_hit()], claims, verifications, insufficient_evidence=False)
    assert breakdown.citation_coverage == 0.5
    assert breakdown.citation_validity == 1.0


def test_contradiction_lowers_evidence_agreement():
    claims = [ExtractedClaim(claim_id="claim_01", claim_text="Claim A", citation_numbers=[1])]
    verifications = [ClaimVerification("claim_01", "Claim A", [1], VerificationLabel.CONTRADICTS, 0.0, "contradicted")]
    breakdown = compute_confidence([_hit()], claims, verifications, insufficient_evidence=False)
    assert breakdown.evidence_agreement == 0.0
    assert breakdown.citation_validity == 0.0


def test_overall_score_is_bounded_0_to_100():
    hits = [_hit(reranker_score=10.0)]
    claims = [ExtractedClaim(claim_id="claim_01", claim_text="Claim A", citation_numbers=[1])]
    verifications = [ClaimVerification("claim_01", "Claim A", [1], VerificationLabel.FULLY_SUPPORTS, 1.0, "matches")]
    breakdown = compute_confidence(hits, claims, verifications, insufficient_evidence=False)
    assert 0.0 <= breakdown.overall_score <= 100.0
