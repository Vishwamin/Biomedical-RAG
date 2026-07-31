"""
Pydantic models used as API request/response contracts.
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"


class HealthResponse(BaseModel):
    status: HealthStatus
    app_name: str
    app_env: str
    embedding_model: str
    reranker_model: str
    llm_provider: str
    llm_model: str
    database_reachable: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChunkingStrategy(str, Enum):
    RECURSIVE_FIXED = "recursive_fixed"
    STRUCTURE_AWARE = "structure_aware"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    document_id: str
    source_filename: str
    document_title: str | None = None
    content_hash: str
    status: DocumentStatus
    page_count: int | None = None
    chunk_count: int = 0
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChunkMetadata(BaseModel):
    chunk_id: str
    document_id: str
    source_filename: str
    document_title: str | None = None
    page_number: int | None = None
    section_heading: str | None = None
    chunk_index: int
    text: str
    character_count: int
    token_count: int | None = None
    chunking_strategy: ChunkingStrategy


# --- Retrieval schemas ---


class DenseRetrievalResult(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    dense_score: float = Field(description="Cosine similarity; higher = more similar.")
    dense_rank: int
    page_number: int | None = None
    section_heading: str | None = None
    document_title: str | None = None
    source_filename: str


class SparseRetrievalResult(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    bm25_score: float
    sparse_rank: int
    page_number: int | None = None
    section_heading: str | None = None
    document_title: str | None = None
    source_filename: str


class FusedRetrievalResult(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    dense_rank: int | None = None
    dense_score: float | None = None
    sparse_rank: int | None = None
    bm25_score: float | None = None
    rrf_score: float
    fused_rank: int
    page_number: int | None = None
    section_heading: str | None = None
    document_title: str | None = None
    source_filename: str


class RerankedResult(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    dense_rank: int | None = None
    dense_score: float | None = None
    sparse_rank: int | None = None
    bm25_score: float | None = None
    rrf_rank: int | None = None
    rrf_score: float | None = None
    reranker_score: float
    final_rank: int
    page_number: int | None = None
    section_heading: str | None = None
    document_title: str | None = None
    source_filename: str


class RetrievalDebugRequest(BaseModel):
    question: str
    dense_top_k: int | None = Field(default=None, description="Overrides DENSE_TOP_K for this request.")
    sparse_top_k: int | None = Field(default=None, description="Overrides SPARSE_TOP_K for this request.")


class RetrievalDebugResponse(BaseModel):
    question: str
    dense_results: list[DenseRetrievalResult]
    sparse_results: list[SparseRetrievalResult]
    fused_results: list[FusedRetrievalResult]
    reranked_results: list[RerankedResult] | None = None
    dense_latency_ms: float
    sparse_latency_ms: float
    rrf_latency_ms: float
    rerank_latency_ms: float | None = None


# --- Generation schemas ---


class GenerationCitation(BaseModel):
    citation_number: int
    chunk_id: str
    document_id: str
    source_filename: str
    document_title: str | None = None
    page_number: int | None = None
    section_heading: str | None = None
    text_snippet: str


# --- Reliability layer schemas ---


class VerificationLabelSchema(str, Enum):
    FULLY_SUPPORTS = "fully_supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    DOES_NOT_SUPPORT = "does_not_support"
    CONTRADICTS = "contradicts"


class ClaimSchema(BaseModel):
    claim_id: str
    claim_text: str
    citation_numbers: list[int]
    verification_label: VerificationLabelSchema | None = Field(
        default=None, description="Null means this claim had no citation to verify against."
    )
    verification_score: float | None = None
    verification_explanation: str | None = None


class ConfidenceBreakdownSchema(BaseModel):
    overall_score: float = Field(description="0-100. An engineering heuristic, not a calibrated probability.")
    label: str = Field(description="High / Moderate / Low")
    retrieval_confidence: float
    citation_coverage: float
    citation_validity: float
    evidence_agreement: float
    answer_completeness: float
    explanation: str


class QueryRequest(BaseModel):
    question: str
    top_k: int | None = Field(default=None, description="Overrides RERANK_TOP_K for this request.")
    include_retrieval_debug: bool = Field(
        default=False, description="If true, includes the full dense/sparse/RRF/reranked breakdown."
    )


class QueryResponse(BaseModel):
    question: str
    answer: str
    insufficient_evidence: bool
    citations: list[GenerationCitation]
    sources: list[str] = Field(description="Deduplicated list of source filenames the answer drew from.")
    claims: list[ClaimSchema] = Field(default_factory=list)
    confidence: float | None = Field(default=None, description="0-100. Null only if generation itself failed.")
    confidence_label: str | None = None
    confidence_breakdown: ConfidenceBreakdownSchema | None = None
    retrieval_debug: RetrievalDebugResponse | None = None
    processing_latency_ms: dict[str, float]


# --- Evaluation schemas ---


class RetrievalModeSchema(str, Enum):
    DENSE_ONLY = "dense_only"
    SPARSE_ONLY = "sparse_only"
    HYBRID_RRF = "hybrid_rrf"
    HYBRID_RRF_RERANK = "hybrid_rrf_rerank"


class EvaluationRunRequest(BaseModel):
    modes: list[RetrievalModeSchema] | None = Field(
        default=None,
        description="Which retrieval modes to run. Omit for just the production mode (hybrid_rrf_rerank). "
        "Pass all four for a full ablation comparison — this multiplies LLM calls by the number of modes.",
    )


class EvaluationRunSummarySchema(BaseModel):
    run_id: str
    retrieval_mode: str
    case_count: int
    metrics: dict[str, float]


class EvaluationRunResponse(BaseModel):
    dataset_case_count: int
    runs: list[EvaluationRunSummarySchema]
    note: str = Field(
        default=(
            "Metrics reflect whatever is in data/evaluation/golden_dataset.json. If that file still contains "
            "the shipped example cases, these numbers are real but meaningless — replace it with real questions "
            "about your own ingested documents first."
        )
    )


class EvaluationResultRow(BaseModel):
    run_id: str
    retrieval_mode: str
    created_at: datetime
    metric_name: str
    metric_value: float


class EvaluationResultsResponse(BaseModel):
    results: list[EvaluationResultRow]


# --- Chat schemas ---


class ChatSummary(BaseModel):
    """Chat metadata without messages — used for the sidebar list."""

    id: str
    title: str
    pinned: bool
    created_at: datetime
    updated_at: datetime


class MessageSchema(BaseModel):
    id: str
    chat_id: str
    role: str  # "user" | "assistant"
    content: str
    confidence: float | None = None
    confidence_label: str | None = None
    confidence_breakdown: ConfidenceBreakdownSchema | None = None
    insufficient_evidence: bool = False
    citations: list[GenerationCitation] = Field(default_factory=list)
    claims: list[ClaimSchema] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    retrieval_debug: RetrievalDebugResponse | None = None
    processing_latency_ms: dict[str, float] | None = None
    created_at: datetime


class ChatDetail(ChatSummary):
    messages: list[MessageSchema] = Field(default_factory=list)


class CreateChatRequest(BaseModel):
    title: str | None = Field(default=None, description="Defaults to 'New Chat' if omitted.")


class RenameChatRequest(BaseModel):
    title: str


class PinChatRequest(BaseModel):
    pinned: bool


class SendMessageRequest(BaseModel):
    content: str
    top_k: int | None = None
    include_retrieval_debug: bool = Field(
        default=True, description="Chat messages default to including retrieval debug so the UI can render it later without rerunning retrieval."
    )


class SendMessageResponse(BaseModel):
    user_message: MessageSchema
    assistant_message: MessageSchema
    chat: ChatSummary
