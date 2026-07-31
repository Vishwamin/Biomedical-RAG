"""
Thin single-provider LLM abstraction (Groq). See docs/architecture.md for
why a full multi-provider abstraction was deliberately not built.
"""

from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import GenerationError


@dataclass
class LLMResponse:
    text: str
    model: str


def _generate_groq(prompt: str, system_prompt: str | None) -> LLMResponse:
    if not settings.groq_api_key:
        raise GenerationError(
            "GROQ_API_KEY is not configured. Set it in your .env file — see .env.example."
        )

    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )
    text = response.choices[0].message.content or ""
    return LLMResponse(text=text, model=settings.llm_model)


def generate(prompt: str, system_prompt: str | None = None) -> LLMResponse:
    if settings.llm_provider == "groq":
        return _generate_groq(prompt, system_prompt)
    raise GenerationError(f"Unsupported LLM provider: {settings.llm_provider}")
