from app.verification.citations import VerificationLabel, verify_claim, verify_claims
from app.verification.claims import ExtractedClaim


def test_verify_claim_with_no_citation_is_not_verified():
    result = verify_claim("claim_01", "An unsupported assertion.", [], evidence_by_number={})
    assert result.label is None
    assert result.score == 0.0


def test_verify_claim_fully_supported_by_matching_evidence():
    evidence_by_number = {1: "Elevated IL-6 biomarker levels were associated with treatment response in patients."}
    result = verify_claim(
        "claim_01", "Elevated IL-6 biomarker levels were associated with treatment response in patients.",
        [1], evidence_by_number,
    )
    assert result.label == VerificationLabel.FULLY_SUPPORTS
    assert result.score == 1.0


def test_verify_claim_unrelated_evidence_does_not_support():
    evidence_by_number = {1: "The weather in Hyderabad was mild during the observation period."}
    result = verify_claim(
        "claim_01",
        "Elevated IL-6 biomarker levels were associated with treatment response in a completely different cohort study.",
        [1], evidence_by_number,
    )
    assert result.label == VerificationLabel.DOES_NOT_SUPPORT
    assert result.score == 0.0


def test_verify_claim_with_missing_citation_number_is_unsupported():
    result = verify_claim("claim_01", "Some claim.", [5], evidence_by_number={1: "unrelated evidence text"})
    assert result.label == VerificationLabel.DOES_NOT_SUPPORT
    assert "does not correspond" in result.explanation


def test_verify_claims_batch_preserves_order_and_claim_ids():
    claims = [
        ExtractedClaim(claim_id="claim_01", claim_text="Biomarker levels rose significantly.", citation_numbers=[1]),
        ExtractedClaim(claim_id="claim_02", claim_text="No citation here at all.", citation_numbers=[]),
    ]
    evidence_by_number = {1: "Biomarker levels rose significantly in the treatment group."}
    results = verify_claims(claims, evidence_by_number)
    assert [r.claim_id for r in results] == ["claim_01", "claim_02"]
    assert results[0].label is not None
    assert results[1].label is None
