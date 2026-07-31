"""
Golden Q&A dataset for evaluation. Version-controlled JSON, not a DB table.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

DEFAULT_DATASET_PATH = Path(__file__).parent.parent.parent / "data" / "evaluation" / "golden_dataset.json"


class QuestionType(str, Enum):
    DIRECT_FACTUAL = "direct_factual"
    MULTI_DOCUMENT_SYNTHESIS = "multi_document_synthesis"
    MULTI_HOP = "multi_hop"
    EXACT_TERMINOLOGY = "exact_terminology"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    AMBIGUOUS = "ambiguous"
    HALLUCINATION_RESISTANCE = "hallucination_resistance"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class EvaluationCase:
    case_id: str
    question: str
    question_type: QuestionType
    difficulty: Difficulty
    is_answerable: bool
    expected_source_filenames: list[str] = field(default_factory=list)
    expected_answer_summary: str | None = None
    notes: str | None = None


def load_dataset(path: Path | None = None) -> list[EvaluationCase]:
    path = path or DEFAULT_DATASET_PATH
    if not path.exists():
        return []

    with open(path) as f:
        raw = json.load(f)

    cases = []
    for entry in raw.get("cases", []):
        cases.append(
            EvaluationCase(
                case_id=entry["case_id"], question=entry["question"],
                question_type=QuestionType(entry["question_type"]), difficulty=Difficulty(entry["difficulty"]),
                is_answerable=entry["is_answerable"],
                expected_source_filenames=entry.get("expected_source_filenames", []),
                expected_answer_summary=entry.get("expected_answer_summary"), notes=entry.get("notes"),
            )
        )
    return cases
