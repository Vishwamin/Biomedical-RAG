"""
Shared citation-number parsing — the single source of truth for
recognizing an inline citation marker in LLM output.

This module exists because of a real bug found during Phase 5 live
end-to-end testing: generator.py and claims.py each independently defined
their own regex, both hardcoded to ASCII brackets only.

In production, the real Groq-hosted model (openai/gpt-oss-120b) was
observed emitting fullwidth CJK-style brackets — [1] rendered as the
fullwidth 【1】 — instead of ASCII [1][2], despite the prompt's evidence
block showing ASCII brackets as the example format. Against an
ASCII-bracket-only pattern this produces zero matches with no error: not
a crash, just a silently empty citation list. That single silent failure
cascaded into four separate-looking symptoms: empty `citations` in the API
response, empty `citation_numbers` on every extracted claim, an empty
`cited_hits` list feeding confidence scoring, and therefore
`retrieval_confidence: 0` and a collapsed final confidence score.
"""

import re

CITATION_REGEX = re.compile(r"[\[\u3010]\s*(\d+)\s*[\]\u3011]")


def find_citation_numbers(text: str) -> list[int]:
    seen: list[int] = []
    for match in CITATION_REGEX.finditer(text):
        n = int(match.group(1))
        if n not in seen:
            seen.append(n)
    return seen


def find_citation_numbers_sorted(text: str) -> list[int]:
    return sorted(set(find_citation_numbers(text)))


def contains_citation(text: str) -> bool:
    return CITATION_REGEX.search(text) is not None
