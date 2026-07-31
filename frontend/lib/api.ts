import type {
  ApiErrorBody,
  ChatDetail,
  ChatSummary,
  ChunkMetadata,
  DocumentMetadata,
  EvaluationResultsResponse,
  EvaluationRunResponse,
  HealthResponse,
  QueryResponse,
  RetrievalMode,
  SendMessageResponse,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null, fallbackMessage: string) {
    super(body?.message || fallbackMessage);
    this.status = status;
    this.body = body;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, null, "Could not reach the BioRAG API. Is the backend running?");
  }

  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = await response.json();
    } catch {
      // response wasn't JSON; body stays null
    }
    throw new ApiError(response.status, body, `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  listDocuments: () => request<DocumentMetadata[]>("/api/v1/documents"),

  getDocument: (documentId: string) => request<DocumentMetadata>(`/api/v1/documents/${documentId}`),

  getDocumentChunks: (documentId: string) =>
    request<ChunkMetadata[]>(`/api/v1/documents/${documentId}/chunks`),

  uploadDocument: (file: File, chunkingStrategy?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    const query = chunkingStrategy ? `?chunking_strategy=${chunkingStrategy}` : "";
    return request<DocumentMetadata>(`/api/v1/documents/upload${query}`, {
      method: "POST",
      body: formData,
    });
  },

  deleteDocument: (documentId: string) =>
    request<{ status: string; document_id: string }>(`/api/v1/documents/${documentId}`, {
      method: "DELETE",
    }),

  query: (question: string, opts?: { topK?: number; includeRetrievalDebug?: boolean }) =>
    request<QueryResponse>("/api/v1/query", {
      method: "POST",
      body: JSON.stringify({
        question,
        top_k: opts?.topK,
        include_retrieval_debug: opts?.includeRetrievalDebug ?? false,
      }),
    }),

  runEvaluation: (modes?: RetrievalMode[]) =>
    request<EvaluationRunResponse>("/api/v1/evaluation/run", {
      method: "POST",
      body: JSON.stringify({ modes: modes ?? null }),
    }),

  listEvaluationResults: () => request<EvaluationResultsResponse>("/api/v1/evaluation/results"),

  getEvaluationRun: (runId: string) =>
    request<EvaluationResultsResponse>(`/api/v1/evaluation/results/${runId}`),

  // --- Chats ---

  createChat: (title?: string) =>
    request<ChatSummary>("/api/v1/chats", {
      method: "POST",
      body: JSON.stringify({ title: title ?? null }),
    }),

  listChats: () => request<ChatSummary[]>("/api/v1/chats"),

  getChat: (chatId: string) => request<ChatDetail>(`/api/v1/chats/${chatId}`),

  deleteChat: (chatId: string) =>
    request<{ status: string; chat_id: string }>(`/api/v1/chats/${chatId}`, { method: "DELETE" }),

  setChatPinned: (chatId: string, pinned: boolean) =>
    request<ChatSummary>(`/api/v1/chats/${chatId}/pin`, {
      method: "PATCH",
      body: JSON.stringify({ pinned }),
    }),

  renameChat: (chatId: string, title: string) =>
    request<ChatSummary>(`/api/v1/chats/${chatId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),

  duplicateChat: (chatId: string) =>
    request<ChatSummary>(`/api/v1/chats/${chatId}/duplicate`, { method: "POST" }),

  sendChatMessage: (chatId: string, content: string, opts?: { topK?: number }) =>
    request<SendMessageResponse>(`/api/v1/chats/${chatId}/messages`, {
      method: "POST",
      body: JSON.stringify({
        content,
        top_k: opts?.topK,
        include_retrieval_debug: true,
      }),
    }),
};
