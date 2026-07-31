import pytest

from app.core.exceptions import GenerationError
from app.core.config import settings
from app.generation.llm import generate


def test_generate_raises_clear_error_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    with pytest.raises(GenerationError, match="GROQ_API_KEY"):
        generate("some prompt")


def test_generate_raises_for_unsupported_provider(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "some_unsupported_provider")
    with pytest.raises(GenerationError, match="Unsupported LLM provider"):
        generate("some prompt")
    monkeypatch.setattr(settings, "llm_provider", "groq")
