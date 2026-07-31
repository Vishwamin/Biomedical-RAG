"""
Central configuration module for BioRAG.

All tunable parameters live here and are loaded from environment variables
(via a .env file in development). Nothing in the rest of the codebase should
hardcode a model name, path, or threshold — it should import `settings` from
this module instead.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App metadata ---
    app_name: str = "BioRAG"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"

    # --- LLM ---
    groq_api_key: str = ""
    llm_provider: str = "groq"
    llm_model: str = "openai/gpt-oss-120b"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024

    # --- Embeddings ---
    embedding_model: str = "pritamdeka/S-PubMedBert-MS-MARCO"
    embedding_device: str = "cpu"

    # --- Reranker ---
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_device: str = "cpu"

    # --- Vector store ---
    chroma_persist_directory: str = "./data/chroma"
    chroma_collection_name: str = "biorag_chunks"

    # --- Storage ---
    database_url: str = "sqlite:///./data/biorag.db"
    documents_directory: str = "./data/documents"

    # --- Retrieval ---
    dense_top_k: int = 15
    sparse_top_k: int = 15
    rrf_k: int = 60
    dense_weight: float = 1.0
    sparse_weight: float = 1.0
    rerank_candidate_k: int = 20
    rerank_top_k: int = 5

    # --- Chunking ---
    chunk_size: int = 800
    chunk_overlap: int = 150
    default_chunking_strategy: str = "structure_aware"

    # --- Reliability thresholds ---
    min_retrieval_confidence: float = 0.35
    confidence_weight_retrieval: float = 0.30
    confidence_weight_citation_validity: float = 0.30
    confidence_weight_citation_coverage: float = 0.20
    confidence_weight_evidence_agreement: float = 0.10
    confidence_weight_answer_completeness: float = 0.10

    # --- CORS ---
    cors_allow_origins: str = "http://localhost:3000"

    # --- Logging ---
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so we parse the environment once."""
    return Settings()


settings = get_settings()
