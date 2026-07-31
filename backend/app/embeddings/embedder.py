"""
Biomedical embedding model wrapper. Model: pritamdeka/S-PubMedBert-MS-MARCO.

The sentence-transformers import is deliberately deferred to inside
_get_model(), so the rest of the codebase can import this module without
requiring torch/HF at all.
"""

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def _get_model():
    from sentence_transformers import SentenceTransformer

    logger.info(
        "loading_embedding_model",
        extra={"event_data": {"model": settings.embedding_model, "device": settings.embedding_device}},
    )
    return SentenceTransformer(settings.embedding_model, device=settings.embedding_device)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
