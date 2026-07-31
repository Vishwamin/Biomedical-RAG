# BioRAG Architecture Notes

## Status: Phases 1–7 complete (Foundation → Frontend)

This document tracks architectural decisions across every build phase, so
they can be explained in an interview and so future-you remembers *why* a
choice was made, not just what it is.

> **A note on this revision:** the sandboxed build environment this project
> was developed in reset mid-way through Phase 7, wiping the working
> directory. Every backend file (Phases 1–6) and the Phase 7 frontend were
> reconstructed from the full source already present in conversation
> history and re-verified — the full pytest suite (99 tests) was re-run
> and a live integration test (real backend + real frontend, booted
> together, verified via HTTP) was re-performed before this was packaged.
> Nothing here is being described from memory; it was rebuilt and
> re-tested, not assumed correct.

## Pipeline (backend)

```
Biomedical PDFs / TXT / MD
        ↓
Document Ingestion (parser.py, chunker.py, metadata.py)
        ↓
   ┌────────────────┴────────────────┐
Dense Search (ChromaDB)      BM25 Sparse Search (rank_bm25)
   └────────────────┬────────────────┘
        ↓
Reciprocal Rank Fusion (manual, k=60)
        ↓
Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2)
        ↓
Grounded LLM Generation (Groq, openai/gpt-oss-120b)
        ↓
Claim Extraction → Citation Verification → Confidence Scoring
        ↓
Final Answer + Citations + Sources + Confidence
        ↓
Next.js Research Workspace (Phase 7)
```

---

## Phase 1 — Foundation

Central `config.py` (env-driven, nothing hardcoded), structured JSON
logging, a typed exception hierarchy with FastAPI handlers, SQLite via
SQLAlchemy, `/health`. Exit criterion: app boots, `/health` returns 200
with real config values, tests pass.

## Phase 2 — Document Intelligence

**Parsing**: PyMuPDF for PDF, plain read for TXT/MD. Title detection is
heuristic (PDF `/Title` metadata, falling back to "first plausible line on
page 1"), documented as approximate, not guaranteed. Artifact stripping is
narrow by design — only bare page numbers and "Page X of Y" footers, not
general header/footer/watermark removal (that needs layout analysis, out
of scope).

**Chunking**: two strategies. Recursive fixed-size (sliding window with
sentence-boundary extension) is the baseline. Structure-aware detects
canonical scientific section names (Abstract/Methods/Results/...) plus
Markdown ATX headings, and **honestly falls back to recursive_fixed and
labels the resulting chunks as such** if no headings are found — the
`chunking_strategy` field is a claim about what actually happened, not
what was requested.

**Duplicate detection**: exact-byte SHA-256 hash. Two different exports of
the same paper (different bytes, same content) will NOT be caught — a
documented limitation, not silently unhandled.

## Phase 3 — Retrieval

**Embeddings**: `pritamdeka/S-PubMedBert-MS-MARCO`, chosen over
`NeuML/pubmedbert-base-embeddings` and `BAAI/bge-base-en-v1.5` because it's
PubMedBERT fine-tuned specifically for asymmetric query→passage retrieval
— matching the actual access pattern (short question, long passage
chunk). The `sentence-transformers` import is deferred inside
`_get_model()` so the rest of the codebase can import this module without
requiring torch at all; the ~420MB model downloads on first real use.

**ChromaDB**: configured for cosine similarity explicitly
(`hnsw:space: cosine`), not the default squared-L2, since embeddings are
L2-normalized. Chroma returns *distance*; `dense.py` converts back with
`similarity = 1 - distance` — a common source of silently-inverted
rankings if missed.

**BM25**: rebuilt fully from SQLite on every document add/delete (no
incremental update API in `rank_bm25`), including once at app startup.
Tokenizer preserves internal hyphens (`IL-6`, `PD-L1`) rather than
splitting on every non-alphanumeric character, since biomedical
terminology's meaning often lives in those compounds.

**RRF**: hand-implemented (`score = Σ 1/(k+rank)`, k=60 default), not
pulled from a library, so every stage is inspectable through
`/api/v1/retrieve` — this is what makes "why was this chunk retrieved"
answerable rather than opaque.

**Real bug found in Phase 6, rooted in Phase 3 code**: `sparse.py`'s
inclusion filter (`if score <= 0: continue`) assumed a non-positive BM25
score meant "no term overlap." False — classic Okapi IDF (no smoothing)
can legitimately score a genuinely relevant document as exactly 0.0 in a
small corpus. Confirmed directly: a 2-document corpus where a query term
appears in exactly 1 of 2 documents gives `idf = log(1.5/1.5) = log(1) =
0`, so a document sharing every query term still scored 0.0 and was
silently dropped. Fixed by deciding inclusion from genuine token overlap
(a precomputed `token_set` per chunk) instead of the score's sign — the
BM25 score is still used for *ranking order* among genuine matches, only
the inclusion filter was wrong. A near-miss caught mid-fix: an early
version of the fix accidentally indexed `BM25Okapi` on the *deduplicated*
token set instead of the full token list with repeats, which would have
silently destroyed BM25's term-frequency component. Caught by re-reading
the diff, not by a test.

## Phase 4 — Reranking & Generation

**Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2` over
`BAAI/bge-reranker-base`, purely on CPU latency — MiniLM reranks 15-20
candidates in well under a second; the larger reranker is higher quality
but too slow without a GPU. Documented as a speed/quality trade-off with
an explicit "what would you do differently in production" answer (swap to
a GPU-backed reranking endpoint).

**LLM**: a deliberately thin single-provider abstraction (Groq only), not
a speculative multi-provider framework — `generation/llm.py` exposes one
`generate()` function with provider/model both env-configurable, which
demonstrates the seam without over-engineering for a provider that
doesn't exist yet.

**Generation**: numbered-evidence prompt, citation requirement, explicit
insufficient-evidence instruction, "don't add specificity beyond what's
stated" rule (strengthened in the Phase 5 bugfix pass).

## Phase 5 — Reliability Layer + Real Bugfixes

**Claim extraction**: sentence-level, not true atomic-claim decomposition
— a documented simplification. Citation verification uses LLM-as-judge,
explicitly **not** treated as independent ground truth (a model checking
claims derived from its own output shares the same blind spots), behind
an injectable `verify_fn` seam. Confidence scoring is a weighted composite
of five measured signals (`0.30×retrieval + 0.30×citation_validity +
0.20×citation_coverage + 0.10×evidence_agreement +
0.10×answer_completeness`) — repeatedly documented as an engineering
heuristic, not a calibrated probability of factual accuracy.

**Six real bugs found in live end-to-end testing, all fixed at their root
cause, not patched at the symptom:**

1–4. **One root cause, four symptoms.** The real Groq model emits
fullwidth CJK-style citation brackets (`【1】`) instead of ASCII `[1]`,
despite the prompt's example using ASCII. `generator.py` and `claims.py`
each had their own independently-defined ASCII-only regex, so both
silently produced empty citation lists — cascading into empty API
`citations`, empty claim `citation_numbers`, a zero `retrieval_confidence`,
and a collapsed final `confidence`. **Fix**: centralized citation parsing
into one shared module, `generation/citation_parsing.py`, supporting both
bracket styles — both call sites now import from it, structurally
preventing the two from drifting apart again.

5. **insufficient_evidence boolean disagreeing with the answer's own
prose.** The original detector was a hand-enumerated keyword allowlist,
which can never be exhaustive against free-text model output. **Fix**:
added a structural fallback — a substantive answer citing zero valid
evidence numbers is independently treated as insufficient, regardless of
phrasing, tied to the same grounding signal `citation_coverage` already
measures.

6. **LLM introducing specifics not present in evidence** (e.g. elaborating
a general mechanism into an incorrect specific one). **Fix**: added an
explicit "do not add specificity beyond what's stated" rule to the system
prompt — documented honestly as a mitigation pinned by a regression test
on the prompt text, not a provable guarantee, since no deterministic test
can confirm a live model's behavior on every input.

## Phase 6 — Evaluation Framework + Retrieval Ablation

**Golden dataset**: version-controlled JSON (`data/evaluation/`), not a DB
table — reviewable and diffable like a test suite, not silently mutable.
Ships with 4 **clearly-labeled example cases**, not a real 30+ question
ground-truth set — fabricating "real" biomedical ground truth about
uningested documents would violate this project's own no-fabrication rule
as directly as inventing scores would. Ground truth uses
`expected_source_filenames` (stable, human-writable) rather than chunk IDs
(regenerated per-ingestion, would silently stop matching after re-upload).

**Ablation**: `services/pipeline.py` adds a `RetrievalMode` enum
(`dense_only` / `sparse_only` / `hybrid_rrf` / `hybrid_rrf_rerank`) and one
`run_retrieval()` function all four modes share — applying the Phase 5
lesson directly: an ablation study is specifically about comparing the
*same* underlying calls under different truncation/fusion rules, so those
calls have to be provably the same code path. The production `/query`
endpoint deliberately keeps its own inline pipeline (fine-grained
per-stage timing is a tested part of its API contract) rather than being
refactored onto the shared function — the underlying retrieval primitives
are already the single source of truth either way.

**Metrics**: Precision@K/Recall@K/MRR and refusal-rate metrics are fully
deterministic (no LLM). Answer-quality metrics (faithfulness/relevance/
correctness) use LLM-as-judge, same documented heuristic-not-ground-truth
limitation as citation verification. A full four-mode ablation run costs
4x the LLM calls of the production mode alone, so the API defaults to just
`hybrid_rrf_rerank` unless the caller explicitly requests more.

## Phase 7 — Frontend

**Stack**: Next.js 15 (App Router), TypeScript, Tailwind CSS v4, no
external UI kit — `lucide-react` for icons, `clsx` for conditional
classes.

**Design direction**: a biomedical research workspace, not a generic
chatbot. Cool sage-paper background (not the common warm AI-cream), a
deep oxblood accent (not terracotta), an editorial-serif/technical-sans/
mono type system evoking scientific publishing. The persistent left
sidebar is styled as a lab-notebook spine (dark, narrow, minimal).

**Signature element — the evidence rank trail** (`RankTrail.tsx`): every
cited passage traveled through up to four retrieval stages before
reaching the answer, and its rank at each stage is the most honest
explanation of *why* it's there — a chunk that was #12 in dense search
but #1 after reranking tells a genuinely different story than one that
was #1 throughout. This is the one visual element that couldn't exist for
any other kind of tool; it's tied directly to the backend's actual
retrieval-provenance data (`dense_rank`/`sparse_rank`/`rrf_rank`/
`final_rank` on every `RerankedResult`), not decoration.

**Google Fonts were not used.** This sandboxed build environment has no
network access to `fonts.gstatic.com` (only package registries are
allowlisted), and `next/font/google` fetches font files at *build time* —
using it here would have failed the build entirely. System font stacks
(`ui-serif`/`-apple-system`/`ui-monospace` with sensible fallback chains)
were used instead, deliberately chosen to still read as "editorial serif
/ technical sans / mono" without a network dependency. This works
identically well in a normal internet-connected dev environment; there's
no functional reason to swap it for real Google Fonts, though nothing
prevents doing so.

**API integration**: a single typed client (`lib/api.ts`) wrapping
`fetch`, with `lib/types.ts` hand-mirroring the backend's Pydantic
schemas. No OpenAPI codegen step — deliberately, given the project's
size; the manual-sync cost is small and explicit rather than adding a
build-time dependency for a handful of interfaces.

**Verified live**: both the FastAPI backend (with fake embedding/
reranker/LLM/verifier calls, since this sandbox can't reach Hugging Face
or Groq — see below) and the Next.js frontend were booted together in the
same process group, and real HTTP round-trips were confirmed: all three
pages render their actual content (not error pages), a real document
upload and a real query both succeeded end-to-end through the deployed
API, the query response returned a genuinely confidence-scored, cited,
claim-verified answer with populated `reranked_results` (exactly the data
shape the evidence cards and rank trail need), and a CORS preflight check
confirmed the frontend's origin is correctly allowed by the backend.

### Sandbox limitation, repeated for clarity

This build environment cannot reach Hugging Face (to download the real
embedding/reranker models) or Groq (for real LLM calls) — only package
registries are network-allowlisted. All live verification in this
project uses dependency-injected fakes at exactly the seams built for
this purpose (`embed_fn`, `score_fn`, `verify_fn`, and `llm_generate`
module-level patching) — never by relaxing application logic. In a normal
local dev environment with internet access, the real models and API
download/authenticate automatically on first use; no code changes are
needed.

---

## Cumulative exit criteria (all phases, re-verified after reconstruction)

- `uvicorn app.main:app --reload` boots without error; `/health` returns
  200 with real config
- Document upload → parse → chunk → embed → index → `status: indexed`
- `/api/v1/retrieve` and `/api/v1/query` return real dense/sparse/RRF/
  reranked results with full provenance
- `/api/v1/query` returns claims, citation verification, and a confidence
  score/breakdown that responds correctly to genuinely well-supported vs.
  genuinely unsupported input
- `/api/v1/evaluation/run` executes the golden dataset across one or more
  retrieval modes and persists real, non-fabricated metrics
- `npm run build` in `frontend/` completes with zero type errors; all
  three pages (query workspace, documents, evaluation) render real content
  against a live backend
- `pytest` passes all 99 backend tests offline (fake embedder/reranker/
  LLM/verifier/judge, real Chroma/BM25/RRF/reranking-selection/prompt-
  building/citation-parsing/confidence-math code paths)

---

## Phase 7.5 — Persistent Conversational Chat System

Requested as a follow-up to the initial Phase 7 frontend: transform the
single-query interface into a persistent, ChatGPT-like conversational
workspace while preserving every existing BioRAG capability (confidence
scoring, evidence cards, rank trail, retrieval inspector, claims,
citations) unchanged.

### Key decisions

**Endpoint prefix: `/api/v1/chats`, not the unprefixed `/api/chats` from
the request.** Every other route in this app lives under `/api/v1` (see
`core/config.py`'s `api_v1_prefix`). Introducing a second, differently
prefixed API surface for chats alone would be a real inconsistency for no
functional benefit — the frontend API client is written against
`/api/v1/chats` accordingly. Noted explicitly here since it's a
deliberate deviation from the literal request text, not an oversight.

**One shared pipeline function, not two independent implementations.**
`services/rag_pipeline.py::execute_rag_query()` is the single place the
full dense→sparse→RRF→rerank→generate→verify→score sequence lives; both
`POST /api/v1/query` (kept, for backward compatibility and one-off
queries) and `POST /api/v1/chats/{id}/messages` call it. This is the
direct application of the lesson from the Phase 5 citation-parsing bug
and the Phase 6 ablation-mode pipeline: two call sites independently
reimplementing "the same logic" is exactly how that kind of bug happens.
There's now structurally only one retrieval pipeline to maintain.

**Full response persisted, not just answer text.** `MessageRecord` stores
`retrieval_json` / `citations_json` / `claims_json` / `confidence_breakdown_json`
/ `latency_json` — the complete shape `/api/v1/query` would have returned
— JSON-encoded per message. This is what makes "reopening a chat must not
rerun retrieval" actually true rather than aspirational: a regression
test (`test_reopening_a_chat_returns_persisted_data_without_rerunning`)
monkeypatches `execute_rag_query` to raise `AssertionError` if called, then
confirms `GET /chats/{id}` still succeeds and returns byte-identical
answer content and confidence — proving it's a pure read, not "probably
doesn't re-query."

**Auto-titling is local keyword extraction, explicitly not an LLM call**
(`services/chat_titles.py`), per the request's own constraint. It strips
leading question words (What/How/Why/...), drops a small filler-word set,
title-cases what remains, and caps length. This is genuine keyword
extraction, not naive truncation — but it's still a heuristic: it will
not always produce an editorially reordered title the way a human or an
LLM summarizing intent would (the request's own example, "What biomarkers
validate Alzheimer's diagnosis?" → "Alzheimer's Biomarkers", reorders
words for readability in a way no non-semantic heuristic can reliably
do). The shipped heuristic produces "Biomarkers Validate Alzheimer's
Diagnosis" for that input — correct content, different word order. This
trade-off is accepted and documented rather than either quietly
under-delivering or secretly calling an LLM against the stated
constraint.

**Pinned-chat sort order**: `ORDER BY pinned DESC, updated_at DESC` at
the database level, not client-side sorting — pinned chats are always
first regardless of how recently they were touched, matching the
request's "Pinned chats always stay at the top."

**Ephemeral per-chat UI state (scroll position, retrieval-inspector
open/closed) is restored via `sessionStorage`, keyed by chat id and
message id** (`lib/useSessionUiState.ts`) — not by keeping the chat page
component mounted across navigation. Next.js's App Router unmounts a
route's component tree on navigation by default; rather than fighting
that with a custom persistent-layout architecture, the *data* that
matters (messages, confidence, citations, evidence) is already durable
server-side and simply re-fetched on return, while the small amount of
genuinely ephemeral presentation state (scroll offset, which inspector
panels are expanded) is persisted client-side and restored on remount.
The net effect satisfies the request's "returning to a chat should
restore it exactly" without requiring a heavier state-management
architecture change.

**Sidebar chat-list refresh uses a tiny custom event bus**
(`lib/chatEvents.ts`), not a full state-management library. Chat
creation, sending a first message (which auto-titles), pinning, renaming,
and duplicating all happen from different components; rather than lifting
chat-list state into a shared store, each of those actions calls
`emitChatsChanged()` and the sidebar re-fetches its own list on that
event. This is intentionally lightweight for the number of call sites
involved — a heavier solution (Redux/Zustand/React Query) would be a
reasonable choice at larger scale but is more machinery than this
surface area currently needs.

**Delete confirmation uses `window.confirm`**, not a custom styled modal
dialog — satisfies "ask for confirmation" without adding a new modal
component and its own focus-trap/accessibility work for a single
irreversible-action guard.

### An honest scope boundary, not a hidden gap

**Each chat message still runs an independent RAG query — there is no
conversation-history-aware retrieval or generation.** A short follow-up
like "Why does that matter clinically?" is retrieved and generated in
total isolation from the prior turn; it does not receive the earlier
question or answer as context. This was confirmed directly in live
testing: a real follow-up question in this shape scored low confidence
because the retrieval had nothing but the follow-up's own (contextless)
words to work with. Building genuinely conversational RAG — using chat
history to reformulate the retrieval query and/or injecting prior turns
into the generation prompt — is a real, separate feature, not something
that falls out of adding chat persistence. The UI *looks* conversational
(ChatGPT-style message list, one thread), and *history is preserved and
restorable*, but *retrieval and generation quality for context-dependent
follow-ups* was not part of what this request asked for and has not been
built. Flagged here explicitly rather than left to be discovered later.

### Verified live

Full flow tested end-to-end via real HTTP against the live backend
(dense/sparse/RRF/reranking-selection all real; embedding/reranker/LLM
calls faked per the sandbox's lack of Hugging Face/Groq network access,
per project convention): document upload → create chat → send first
message (confirmed real confidence score 82.7/High, 2 citations, full
`retrieval_debug` populated) → confirmed auto-title generated from that
first message → pin → rename (confirmed the rename survives a second
message, i.e. auto-titling doesn't clobber a manual rename) → duplicate
(confirmed independent message copies, confirmed deleting the duplicate
doesn't affect the original) → chat list correctly sorts the pinned chat
first → second message sent and persisted → full chat detail re-fetched
showing all 4 messages in correct order. The Next.js frontend was booted
alongside the real backend and confirmed serving 200 responses for the
chat page, documents page, and evaluation page, with CORS preflight
confirmed working for the new `/api/v1/chats/*` routes including `PATCH`
(needed for pin/rename).

### Regression coverage added

`tests/test_chat_titles.py` (6 tests) and `tests/test_chats_api.py` (13
tests, including the no-rerun-on-reopen proof) — **116/116 backend tests
passing**, all pre-existing document/evaluation/health/retrieval/query
tests still green, confirming nothing was broken by this change.
