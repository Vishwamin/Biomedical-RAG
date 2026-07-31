"""
Grounded answer generation.
"""

from dataclasses import dataclass

from app.core.exceptions import GenerationError
from app.core.logging import get_logger
from app.generation.citation_parsing import find_citation_numbers
from app.generation.llm import generate as llm_generate
from app.generation.prompts import SYSTEM_PROMPT, build_generation_prompt
from app.retrieval.reranker import RerankedHit

logger = get_logger(__name__)

_INSUFFICIENT_EVIDENCE_PHRASES = [
    "insufficient evidence", "does not contain enough information", "do not contain enough information",
    "not contain sufficient", "cannot be answered", "can't be answered", "not enough information",
    "no relevant evidence", "insufficient information", "does not specify", "does not provide",
    "no information", "not specified in the", "not mentioned in the", "not available in the",
    "evidence does not", "evidence do not", "does not include",
]


@dataclass
class GeneratedAnswer:
    answer_text: str
    cited_numbers: set[int]
    insufficient_evidence: bool
    raw_model_output: str


def generate_grounded_answer(question: str, evidence_hits: list[RerankedHit]) -> GeneratedAnswer:
    if not evidence_hits:
        return GeneratedAnswer(
            answer_text=(
                "No relevant documents have been ingested yet, so this question "
                "cannot be answered from the available literature."
            ),
            cited_numbers=set(), insufficient_evidence=True, raw_model_output="",
        )

    evidence_chunks = [
        {
            "number": i + 1, "text": hit.text, "source_filename": hit.source_filename,
            "document_title": hit.document_title, "page_number": hit.page_number,
            "section_heading": hit.section_heading,
        }
        for i, hit in enumerate(evidence_hits)
    ]

    prompt = build_generation_prompt(question, evidence_chunks)

    try:
        llm_response = llm_generate(prompt, system_prompt=SYSTEM_PROMPT)
    except GenerationError:
        raise
    except Exception as exc:
        raise GenerationError(f"Answer generation failed: {exc}") from exc

    answer_text = (llm_response.text or "").strip()

    valid_numbers = {c["number"] for c in evidence_chunks}
    cited_numbers = {n for n in find_citation_numbers(answer_text) if n in valid_numbers}

    lower_answer = answer_text.lower()
    phrase_signal = any(phrase in lower_answer for phrase in _INSUFFICIENT_EVIDENCE_PHRASES)
    ungrounded_signal = not cited_numbers
    insufficient = phrase_signal or ungrounded_signal

    logger.info(
        "grounded_answer_generated",
        extra={
            "event_data": {
                "evidence_count": len(evidence_hits), "cited_count": len(cited_numbers),
                "insufficient_evidence": insufficient, "insufficient_via_phrase": phrase_signal,
                "insufficient_via_no_citations": ungrounded_signal, "answer_length": len(answer_text),
            }
        },
    )

    return GeneratedAnswer(
        answer_text=answer_text, cited_numbers=cited_numbers,
        insufficient_evidence=insufficient, raw_model_output=llm_response.text,
    )
