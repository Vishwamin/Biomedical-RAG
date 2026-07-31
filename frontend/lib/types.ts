export type DocumentStatus = "pending" | "processing" | "indexed" | "failed";
export type ChunkingStrategy = "recursive_fixed" | "structure_aware";

export interface DocumentMetadata {
  document_id: string;
  source_filename: string;
  document_title: string | null;
  content_hash: string;
  status: DocumentStatus;
  page_count: number | null;
  chunk_count: number;
  uploaded_at: string;
}

export interface ChunkMetadata {
  chunk_id: string;
  document_id: string;
  source_filename: string;
  document_title: string | null;
  page_number: number | null;
  section_heading: string | null;
  chunk_index: number;
  text: string;
  character_count: number;
  token_count: number | null;
  chunking_strategy: ChunkingStrategy;
}

export interface DenseRetrievalResult {
  chunk_id: string;
  document_id: string;
  text: string;
  dense_score: number;
  dense_rank: number;
  page_number: number | null;
  section_heading: string | null;
  document_title: string | null;
  source_filename: string;
}

export interface SparseRetrievalResult {
  chunk_id: string;
  document_id: string;
  text: string;
  bm25_score: number;
  sparse_rank: number;
  page_number: number | null;
  section_heading: string | null;
  document_title: string | null;
  source_filename: string;
}

export interface FusedRetrievalResult {
  chunk_id: string;
  document_id: string;
  text: string;
  dense_rank: number | null;
  dense_score: number | null;
  sparse_rank: number | null;
  bm25_score: number | null;
  rrf_score: number;
  fused_rank: number;
  page_number: number | null;
  section_heading: string | null;
  document_title: string | null;
  source_filename: string;
}

export interface RerankedResult {
  chunk_id: string;
  document_id: string;
  text: string;
  dense_rank: number | null;
  dense_score: number | null;
  sparse_rank: number | null;
  bm25_score: number | null;
  rrf_rank: number | null;
  rrf_score: number | null;
  reranker_score: number;
  final_rank: number;
  page_number: number | null;
  section_heading: string | null;
  document_title: string | null;
  source_filename: string;
}

export interface RetrievalDebugResponse {
  question: string;
  dense_results: DenseRetrievalResult[];
  sparse_results: SparseRetrievalResult[];
  fused_results: FusedRetrievalResult[];
  reranked_results: RerankedResult[] | null;
  dense_latency_ms: number;
  sparse_latency_ms: number;
  rrf_latency_ms: number;
  rerank_latency_ms?: number;
}

export type VerificationLabel =
  | "fully_supports"
  | "partially_supports"
  | "does_not_support"
  | "contradicts";

export interface ClaimSchema {
  claim_id: string;
  claim_text: string;
  citation_numbers: number[];
  verification_label: VerificationLabel | null;
  verification_score: number | null;
  verification_explanation: string | null;
}

export interface ConfidenceBreakdown {
  overall_score: number;
  label: string;
  retrieval_confidence: number;
  citation_coverage: number;
  citation_validity: number;
  evidence_agreement: number;
  answer_completeness: number;
  explanation: string;
}

export interface GenerationCitation {
  citation_number: number;
  chunk_id: string;
  document_id: string;
  source_filename: string;
  document_title: string | null;
  page_number: number | null;
  section_heading: string | null;
  text_snippet: string;
}

export interface QueryResponse {
  question: string;
  answer: string;
  insufficient_evidence: boolean;
  citations: GenerationCitation[];
  sources: string[];
  claims: ClaimSchema[];
  confidence: number | null;
  confidence_label: string | null;
  confidence_breakdown: ConfidenceBreakdown | null;
  retrieval_debug: RetrievalDebugResponse | null;
  processing_latency_ms: Record<string, number>;
}

export type RetrievalMode = "dense_only" | "sparse_only" | "hybrid_rrf" | "hybrid_rrf_rerank";

export interface EvaluationRunSummary {
  run_id: string;
  retrieval_mode: string;
  case_count: number;
  metrics: Record<string, number>;
}

export interface EvaluationRunResponse {
  dataset_case_count: number;
  runs: EvaluationRunSummary[];
  note: string;
}

export interface EvaluationResultRow {
  run_id: string;
  retrieval_mode: string;
  created_at: string;
  metric_name: string;
  metric_value: number;
}

export interface EvaluationResultsResponse {
  results: EvaluationResultRow[];
}

export interface HealthResponse {
  status: "ok" | "degraded";
  app_name: string;
  app_env: string;
  embedding_model: string;
  reranker_model: string;
  llm_provider: string;
  llm_model: string;
  database_reachable: boolean;
  timestamp: string;
}

export interface ApiErrorBody {
  error: string;
  message: string;
  details: Record<string, unknown>;
}

// --- Chat types ---

export interface ChatSummary {
  id: string;
  title: string;
  pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface MessageSchema {
  id: string;
  chat_id: string;
  role: "user" | "assistant";
  content: string;
  confidence: number | null;
  confidence_label: string | null;
  confidence_breakdown: ConfidenceBreakdown | null;
  insufficient_evidence: boolean;
  citations: GenerationCitation[];
  claims: ClaimSchema[];
  sources: string[];
  retrieval_debug: RetrievalDebugResponse | null;
  processing_latency_ms: Record<string, number> | null;
  created_at: string;
}

export interface ChatDetail extends ChatSummary {
  messages: MessageSchema[];
}

export interface SendMessageResponse {
  user_message: MessageSchema;
  assistant_message: MessageSchema;
  chat: ChatSummary;
}
