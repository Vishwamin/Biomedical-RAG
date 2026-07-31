"""
Shared test fixtures. Three things are patched globally for the whole test
session: this sandboxed environment has no network access to Hugging Face
or Groq, so the real embedding model, cross-encoder reranker, and LLM API
calls are replaced with deterministic, dependency-free fakes. This keeps
the test suite fast and fully offline while still exercising the *real*
ChromaDB storage, BM25, RRF, reranking-selection, and prompt/citation-
parsing code paths — only the actual model inference is faked.
"""

import hashlib
import json
import re

import pytest

_VOCAB_SIZE = 128


def _fake_vector(text: str) -> list[float]:
    vec = [0.0] * _VOCAB_SIZE
    for word in text.lower().split():
        idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % _VOCAB_SIZE
        vec[idx] += 1.0
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
    return [_fake_vector(t) for t in texts]


def _fake_embed_query(query: str) -> list[float]:
    return _fake_vector(query)


def _fake_score_pairs(query: str, passages: list[str]) -> list[float]:
    query_words = set(query.lower().split())
    scores = []
    for passage in passages:
        passage_words = set(passage.lower().split())
        overlap = len(query_words & passage_words)
        scores.append(overlap / max(len(query_words), 1))
    return scores


def _fake_llm_generate(prompt: str, system_prompt: str | None = None):
    from app.generation.llm import LLMResponse

    numbers = sorted({int(n) for n in re.findall(r"^\[(\d+)\]", prompt, flags=re.MULTILINE)})
    if not numbers:
        text = "The available evidence does not contain enough information to answer this question."
    else:
        citation_tags = "".join(f"[{n}]" for n in numbers)
        text = f"Based on the retrieved evidence, this is a synthesized finding {citation_tags}."
    return LLMResponse(text=text, model="fake-test-model")


_VERIFIER_EVIDENCE_REGEX = re.compile(r"EVIDENCE \[\d+\]:\n(.*?)(?=\n\nEVIDENCE \[\d+\]:|\n\nCLAIM:|$)", re.DOTALL)
_VERIFIER_CLAIM_REGEX = re.compile(r"CLAIM:\n(.*)", re.DOTALL)


def _fake_verify_fn(prompt: str, system_prompt: str | None = None):
    from app.generation.llm import LLMResponse

    claim_match = _VERIFIER_CLAIM_REGEX.search(prompt)
    claim_text = claim_match.group(1).strip() if claim_match else ""
    evidence_blocks = _VERIFIER_EVIDENCE_REGEX.findall(prompt)

    claim_words = set(claim_text.lower().split())
    best_overlap_ratio = 0.0
    for block in evidence_blocks:
        evidence_words = set(block.lower().split())
        if not claim_words:
            continue
        overlap_ratio = len(claim_words & evidence_words) / len(claim_words)
        best_overlap_ratio = max(best_overlap_ratio, overlap_ratio)

    if best_overlap_ratio >= 0.5:
        label = "fully_supports"
    elif best_overlap_ratio >= 0.2:
        label = "partially_supports"
    else:
        label = "does_not_support"

    payload = json.dumps({"label": label, "explanation": f"word overlap ratio {best_overlap_ratio:.2f}"})
    return LLMResponse(text=payload, model="fake-test-model")


def _fake_judge_fn(prompt: str, system_prompt: str | None = None):
    from app.generation.llm import LLMResponse

    payload = json.dumps(
        {"faithfulness": 0.8, "relevance": 0.8, "correctness": 0.7, "explanation": "fake judge heuristic"}
    )
    return LLMResponse(text=payload, model="fake-test-model")


@pytest.fixture(autouse=True, scope="session")
def _patch_embeddings_and_chroma_dir(tmp_path_factory):
    import app.retrieval.dense as dense_module
    from app.core.config import settings

    settings.chroma_persist_directory = str(tmp_path_factory.mktemp("chroma"))
    dense_module.reset_client()
    dense_module.embed_texts = _fake_embed_texts
    dense_module.embed_query = _fake_embed_query
    yield


@pytest.fixture(autouse=True, scope="session")
def _patch_reranker_and_llm():
    import app.retrieval.reranker as reranker_module
    import app.generation.generator as generator_module
    import app.verification.citations as citations_module
    import app.generation.llm as llm_module

    reranker_module.score_pairs = _fake_score_pairs
    generator_module.llm_generate = _fake_llm_generate
    citations_module.llm_generate = _fake_verify_fn
    llm_module.generate = _fake_judge_fn
    yield
