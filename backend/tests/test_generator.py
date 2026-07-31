from app.generation.generator import generate_grounded_answer
from app.generation.llm import LLMResponse
from app.retrieval.reranker import RerankedHit


def _hit(chunk_id, text):
    return RerankedHit(
        chunk_id=chunk_id, document_id="docA", text=text, dense_rank=1, dense_score=0.8, sparse_rank=1,
        bm25_score=3.0, rrf_rank=1, rrf_score=0.02, reranker_score=1.5, final_rank=1, page_number=1,
        section_heading="Results", document_title="Doc", source_filename="doc.pdf",
    )


def test_generate_grounded_answer_with_no_evidence_returns_insufficient():
    result = generate_grounded_answer("question", [])
    assert result.insufficient_evidence is True
    assert result.cited_numbers == set()


def test_generate_grounded_answer_detects_insufficient_evidence_phrase(monkeypatch):
    import app.generation.generator as generator_module

    def fake_llm(prompt, system_prompt=None):
        return LLMResponse(text="The evidence does not contain enough information to answer this question.", model="fake")

    monkeypatch.setattr(generator_module, "llm_generate", fake_llm)
    hits = [_hit("c1", "unrelated text")]
    result = generate_grounded_answer("question", hits)
    assert result.insufficient_evidence is True


def test_regression_parses_fullwidth_bracket_citations(monkeypatch):
    """Real bug: the Groq model emitted fullwidth brackets instead of ASCII."""
    import app.generation.generator as generator_module

    def fake_llm(prompt, system_prompt=None):
        return LLMResponse(text="This finding is supported \u30101\u3011 and further confirmed \u30102\u3011.", model="fake")

    monkeypatch.setattr(generator_module, "llm_generate", fake_llm)
    hits = [_hit("c1", "text one"), _hit("c2", "text two")]
    result = generate_grounded_answer("question", hits)
    assert result.cited_numbers == {1, 2}
    assert result.insufficient_evidence is False


def test_regression_insufficient_evidence_without_matching_keyword_phrase(monkeypatch):
    """Real bug: structural fallback must catch zero-citation answers regardless of wording."""
    import app.generation.generator as generator_module

    def fake_llm(prompt, system_prompt=None):
        return LLMResponse(
            text="Recommended dosing regimens for this specific patient population are outside the scope of what was retrieved.",
            model="fake",
        )

    monkeypatch.setattr(generator_module, "llm_generate", fake_llm)
    hits = [_hit("c1", "unrelated background text about a different topic entirely")]
    result = generate_grounded_answer("What dosage should be administered?", hits)
    assert result.insufficient_evidence is True
    assert result.cited_numbers == set()


def test_regression_grounded_answer_with_citations_is_never_flagged_insufficient(monkeypatch):
    import app.generation.generator as generator_module

    def fake_llm(prompt, system_prompt=None):
        return LLMResponse(text="This is well supported by the evidence [1].", model="fake")

    monkeypatch.setattr(generator_module, "llm_generate", fake_llm)
    hits = [_hit("c1", "supporting text")]
    result = generate_grounded_answer("question", hits)
    assert result.insufficient_evidence is False
    assert result.cited_numbers == {1}


def test_regression_system_prompt_forbids_added_specificity():
    from app.generation.prompts import SYSTEM_PROMPT
    lowered = SYSTEM_PROMPT.lower()
    assert "not explicitly stated in the evidence" in lowered
    assert "ascii square brackets" in lowered
