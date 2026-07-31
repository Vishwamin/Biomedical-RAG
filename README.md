# BioRAG — Biomedical AI-Powered Research Intelligence System

A biomedical research intelligence system that uses hybrid retrieval
(dense + BM25 fused via Reciprocal Rank Fusion), cross-encoder reranking,
grounded generation, citation verification, confidence scoring, and a
retrieval-ablation evaluation framework to provide reliable,
evidence-backed answers from scientific literature — with a research
workspace frontend to go with it.

> **Status: Phase 7 — Frontend complete, now with persistent chat.** The
> full backend pipeline (ingestion → hybrid retrieval → reranking →
> grounded generation → claim extraction → citation verification →
> confidence scoring → evaluation) and a Next.js research workspace with
> a persistent, ChatGPT-style conversation system are all working end to
> end. Docker and final packaging (Phase 8) are not yet done — see
> `docs/architecture.md` for the build plan and every architectural
> decision made along the way.

## Disclaimer

This is a research and educational literature-analysis tool. It is **not**
a medical diagnosis system, a clinical decision-making tool, or a
replacement for healthcare professionals.

## Project structure

```
biorag/
├── backend/        FastAPI app — see backend/app/
├── frontend/        Next.js research workspace — see frontend/app/
├── docs/             architecture.md (full decision log across all phases)
└── docker-compose.yml   (Phase 8, not yet added)
```

## Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # add your real GROQ_API_KEY
uvicorn app.main:app --reload
```

Verify: `curl http://localhost:8000/health` should return `"status": "ok"`.

> **Note:** the first document you upload triggers a one-time ~420MB
> download of the embedding model from Hugging Face (and a smaller
> download for the reranker on first query). Requires internet access;
> cached locally afterward.

Run the backend test suite:

```bash
cd backend
pytest -v
```

116 tests, all offline (embedding/reranker/LLM calls are faked at
well-defined injection seams — see `tests/conftest.py` — while ChromaDB,
BM25, RRF, reranking-selection, prompt-building, citation-parsing, and
confidence-math all run for real).

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local        # points at http://localhost:8000 by default
npm run dev
```

Open `http://localhost:3000`. Make sure the backend is running first —
the frontend has nothing to talk to otherwise. Landing on `/` creates a
new chat and redirects into it, same as clicking "New Chat."

Pages:
- **`/chat/[chatId]`** — the conversational research workspace. Ask a
  question, watch the pipeline stages run, get a grounded answer with
  clickable inline citations, a confidence score with an expandable
  breakdown, evidence cards showing each source's rank journey through
  dense/sparse/RRF/reranking, and an optional retrieval inspector — for
  *every* message in the conversation, not just the last one. Chats
  persist to SQLite; reopening one re-renders exactly what's stored
  without rerunning retrieval or generation.
- **`/documents`** — upload PDFs/TXT/MD, see ingestion status, expand any
  document to inspect exactly how it was chunked (section, page,
  strategy), delete documents.
- **`/evaluation`** — run the golden Q&A dataset through the pipeline
  (production mode, or a full 4-mode ablation comparison), see real
  metrics. Shows "No evaluation run yet" honestly until a run actually
  completes — nothing here is ever fabricated.

**Chat sidebar**: pinned chats always sort first, then most-recently
updated. New chats auto-title from the first message (local keyword
extraction — no extra LLM call). Each chat has a `⋯` menu for pin/unpin,
rename, duplicate, and delete (with confirmation). `Ctrl/⌘+N` starts a
new chat from anywhere; `Ctrl/⌘+Shift+O` opens chat search.

> **Known scope boundary:** each message in a chat runs an independent
> RAG query — retrieval and generation do not use prior turns as context.
> Chat history is fully preserved and displayed, but a short follow-up
> like "why?" won't retrieve well on its own, the same way it wouldn't
> against a search engine with no memory. Context-aware follow-up
> retrieval is a real, separate feature that hasn't been built yet — see
> `docs/architecture.md` for detail.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation: config, logging, DB, `/health` | ✅ done |
| 2 | Document ingestion: PDF/TXT/MD parsing, structure-aware chunking | ✅ done |
| 3 | Retrieval: embeddings, ChromaDB, BM25, RRF | ✅ done |
| 4 | Cross-encoder reranking, grounded generation | ✅ done |
| 5 | Claim extraction, citation verification, confidence scoring | ✅ done |
| 6 | Evaluation framework + retrieval ablation study | ✅ done |
| 7 | Next.js frontend + persistent chat system | ✅ done |
| 8 | Tests, Docker, final docs | ⏳ next |

## Trying the full pipeline

```bash
# Upload a paper
curl -X POST http://localhost:8000/api/v1/documents/upload -F "file=@/path/to/paper.pdf"

# Ask a question — full pipeline, with claims/verification/confidence
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What evidence exists regarding X?", "include_retrieval_debug": true}'

# Run evaluation (replace the shipped example cases in
# data/evaluation/golden_dataset.json with real questions first)
curl -X POST http://localhost:8000/api/v1/evaluation/run \
  -H "Content-Type: application/json" \
  -d '{"modes": ["dense_only", "sparse_only", "hybrid_rrf", "hybrid_rrf_rerank"]}'
```

Or just open `http://localhost:3000` and do all of this through the UI.

Evaluation numbers and ablation results depend entirely on what you've
actually ingested and put in the golden dataset — no fabricated metrics
are included anywhere in this repo, at any phase.

## Trying the chat API directly

```bash
# Create a chat
curl -X POST http://localhost:8000/api/v1/chats -H "Content-Type: application/json" -d '{}'

# Send a message (runs the full pipeline, persists both messages)
curl -X POST http://localhost:8000/api/v1/chats/{chat_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "What evidence exists regarding X?"}'

# List chats (pinned first, then most recently updated)
curl http://localhost:8000/api/v1/chats

# Reopen a chat — reads persisted data, does NOT rerun retrieval or generation
curl http://localhost:8000/api/v1/chats/{chat_id}

# Pin, rename, duplicate, delete
curl -X PATCH http://localhost:8000/api/v1/chats/{chat_id}/pin -d '{"pinned": true}'
curl -X PATCH http://localhost:8000/api/v1/chats/{chat_id} -d '{"title": "My Chat"}'
curl -X POST http://localhost:8000/api/v1/chats/{chat_id}/duplicate
curl -X DELETE http://localhost:8000/api/v1/chats/{chat_id}
```
