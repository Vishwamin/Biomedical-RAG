"""
Citation verification (LLM-as-judge, documented as a heuristic not ground truth).
"""

import json
import re
from dataclasses import dataclass
from enum import Enum

from app.core.logging import get_logger
from app.generation.llm import generate as llm_generate

logger = get_logger(__name__)


class VerificationLabel(str, Enum):
    FULLY_SUPPORTS = "fully_supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    DOES_NOT_SUPPORT = "does_not_support"
    CONTRADICTS = "contradicts"


_LABEL_SCORES = {
    VerificationLabel.FULLY_SUPPORTS: 1.0,
    VerificationLabel.PARTIALLY_SUPPORTS: 0.5,
    VerificationLabel.DOES_NOT_SUPPORT: 0.0,
    VerificationLabel.CONTRADICTS: 0.0,
}

VERIFIER_SYSTEM_PROMPT = """You are a strict fact-checking judge. You will be given a CLAIM and one or more EVIDENCE passages that were cited as support for it. Decide whether the evidence actually supports the claim.

Respond with ONLY a JSON object, no other text:
{"label": "fully_supports" | "partially_supports" | "does_not_support" | "contradicts", "explanation": "one short sentence"}

Rules:
- fully_supports: the evidence directly and completely supports the claim.
- partially_supports: the evidence is related and lends some support, but doesn't fully confirm the specific claim as stated.
- does_not_support: the evidence is unrelated or insufficient to judge the claim.
- contradicts: the evidence directly contradicts the claim."""


@dataclass
class ClaimVerification:
    claim_id: str
    claim_text: str
    citation_numbers: list[int]
    label: VerificationLabel | None
    score: float
    explanation: str


def _build_verification_prompt(claim_text: str, evidence_texts: list[str]) -> str:
    evidence_block = "\n\n".join(f"EVIDENCE [{i + 1}]:\n{text}" for i, text in enumerate(evidence_texts))
    return f"{evidence_block}\n\nCLAIM:\n{claim_text}"


def _parse_verifier_response(raw_text: str) -> tuple[VerificationLabel, str]:
    try:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        payload = json.loads(match.group(0) if match else raw_text)
        label = VerificationLabel(payload.get("label", "does_not_support"))
        explanation = str(payload.get("explanation", "")).strip()[:300]
        return label, explanation
    except Exception:
        return VerificationLabel.DOES_NOT_SUPPORT, "Could not parse verifier output; treated as unsupported."


def verify_claim(
    claim_id: str, claim_text: str, citation_numbers: list[int],
    evidence_by_number: dict[int, str], verify_fn=None,
) -> ClaimVerification:
    if not citation_numbers:
        return ClaimVerification(
            claim_id=claim_id, claim_text=claim_text, citation_numbers=[], label=None, score=0.0,
            explanation="No citation attached to this claim — nothing to verify against.",
        )

    verify_fn = verify_fn or llm_generate
    evidence_texts = [evidence_by_number[n] for n in citation_numbers if n in evidence_by_number]
    if not evidence_texts:
        return ClaimVerification(
            claim_id=claim_id, claim_text=claim_text, citation_numbers=citation_numbers,
            label=VerificationLabel.DOES_NOT_SUPPORT, score=0.0,
            explanation="Cited evidence number does not correspond to any retrieved passage.",
        )

    prompt = _build_verification_prompt(claim_text, evidence_texts)
    try:
        response = verify_fn(prompt, system_prompt=VERIFIER_SYSTEM_PROMPT)
        label, explanation = _parse_verifier_response(response.text)
    except Exception as exc:
        logger.error("citation_verification_failed", extra={"event_data": {"error": str(exc)}})
        label, explanation = VerificationLabel.DOES_NOT_SUPPORT, "Verification call failed; treated as unsupported."

    return ClaimVerification(
        claim_id=claim_id, claim_text=claim_text, citation_numbers=citation_numbers,
        label=label, score=_LABEL_SCORES[label], explanation=explanation,
    )


def verify_claims(claims: list, evidence_by_number: dict[int, str], verify_fn=None) -> list[ClaimVerification]:
    return [
        verify_claim(c.claim_id, c.claim_text, c.citation_numbers, evidence_by_number, verify_fn=verify_fn)
        for c in claims
    ]
