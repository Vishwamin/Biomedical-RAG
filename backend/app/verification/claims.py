"""
Claim extraction.
"""

import re
from dataclasses import dataclass

from app.generation.citation_parsing import find_citation_numbers_sorted

_SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[\u3010])")
_MIN_CLAIM_LENGTH = 15


@dataclass
class ExtractedClaim:
    claim_id: str
    claim_text: str
    citation_numbers: list[int]


def extract_claims(answer_text: str) -> list[ExtractedClaim]:
    if not answer_text or not answer_text.strip():
        return []

    sentences = _SENTENCE_SPLIT_REGEX.split(answer_text.strip())
    claims: list[ExtractedClaim] = []
    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if len(sentence) < _MIN_CLAIM_LENGTH:
            continue
        claims.append(
            ExtractedClaim(
                claim_id=f"claim_{i + 1:02d}", claim_text=sentence,
                citation_numbers=find_citation_numbers_sorted(sentence),
            )
        )
    return claims
