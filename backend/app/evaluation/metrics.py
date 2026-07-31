"""
Evaluation metrics.
"""

import json
import re
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


def precision_at_k(retrieved_filenames: list[str], expected_filenames: set[str], k: int) -> float:
    if not expected_filenames:
        return 0.0
    top_k = retrieved_filenames[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for f in top_k if f in expected_filenames)
    return hits / len(top_k)


def recall_at_k(retrieved_filenames: list[str], expected_filenames: set[str], k: int) -> float:
    if not expected_filenames:
        return 0.0
    top_k = set(retrieved_filenames[:k])
    hits = len(top_k & expected_filenames)
    return hits / len(expected_filenames)


def mean_reciprocal_rank(retrieved_filenames: list[str], expected_filenames: set[str]) -> float:
    if not expected_filenames:
        return 0.0
    for rank, filename in enumerate(retrieved_filenames, start=1):
        if filename in expected_filenames:
            return 1.0 / rank
    return 0.0


@dataclass
class RefusalOutcome:
    correct_refusal: bool | None
    false_refusal: bool | None


def evaluate_refusal(is_answerable: bool, insufficient_evidence: bool) -> RefusalOutcome:
    if not is_answerable:
        return RefusalOutcome(correct_refusal=insufficient_evidence, false_refusal=None)
    return RefusalOutcome(correct_refusal=None, false_refusal=insufficient_evidence)


_QUALITY_JUDGE_SYSTEM_PROMPT = """You are grading a generated answer against a question and (optionally) a human-written gist of what a correct answer should cover. Score three dimensions from 0.0 to 1.0:

- faithfulness: does the answer avoid contradicting or overstating the evidence it cites (judge from the answer's own claims and hedging, not outside knowledge)?
- relevance: does the answer actually address what was asked?
- correctness: if a reference gist is provided, does the answer's substance match it? If no gist is provided, judge plausibility and internal consistency only.

Respond with ONLY a JSON object, no other text:
{"faithfulness": 0.0-1.0, "relevance": 0.0-1.0, "correctness": 0.0-1.0, "explanation": "one short sentence"}"""


@dataclass
class AnswerQualityScore:
    faithfulness: float
    relevance: float
    correctness: float
    explanation: str


def _parse_quality_response(raw_text: str) -> AnswerQualityScore:
    try:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        payload = json.loads(match.group(0) if match else raw_text)
        return AnswerQualityScore(
            faithfulness=max(0.0, min(1.0, float(payload.get("faithfulness", 0.0)))),
            relevance=max(0.0, min(1.0, float(payload.get("relevance", 0.0)))),
            correctness=max(0.0, min(1.0, float(payload.get("correctness", 0.0)))),
            explanation=str(payload.get("explanation", ""))[:300],
        )
    except Exception:
        return AnswerQualityScore(0.0, 0.0, 0.0, "Could not parse judge output.")


def judge_answer_quality(
    question: str, answer_text: str, expected_answer_summary: str | None, judge_fn=None,
) -> AnswerQualityScore:
    from app.generation.llm import generate as default_judge_fn

    judge_fn = judge_fn or default_judge_fn

    gist_block = (
        f"Reference gist (what a correct answer should cover): {expected_answer_summary}"
        if expected_answer_summary
        else "No reference gist provided — judge plausibility and internal consistency only."
    )
    prompt = f"Question: {question}\n\nGenerated answer: {answer_text}\n\n{gist_block}"

    try:
        response = judge_fn(prompt, system_prompt=_QUALITY_JUDGE_SYSTEM_PROMPT)
        return _parse_quality_response(response.text)
    except Exception as exc:
        logger.error("answer_quality_judge_failed", extra={"event_data": {"error": str(exc)}})
        return AnswerQualityScore(0.0, 0.0, 0.0, "Judge call failed.")
