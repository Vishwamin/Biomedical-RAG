"""
BM25 sparse (keyword) retrieval.
"""

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.database import ChunkRecord

logger = get_logger(__name__)

_TOKEN_REGEX = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_REGEX.findall(text)]


@dataclass
class SparseHit:
    chunk_id: str
    document_id: str
    text: str
    bm25_score: float
    sparse_rank: int
    page_number: int | None
    section_heading: str | None
    document_title: str | None
    source_filename: str


@dataclass
class _IndexedChunk:
    chunk_id: str
    document_id: str
    text: str
    page_number: int | None
    section_heading: str | None
    document_title: str | None
    source_filename: str
    token_set: frozenset


class BM25Store:
    def __init__(self):
        self._bm25: BM25Okapi | None = None
        self._chunks: list[_IndexedChunk] = []

    @property
    def is_built(self) -> bool:
        return self._bm25 is not None

    def refresh(self, db: Session) -> None:
        records = db.query(ChunkRecord).order_by(ChunkRecord.chunk_id).all()
        self._chunks = [
            _IndexedChunk(
                chunk_id=r.chunk_id, document_id=r.document_id, text=r.text, page_number=r.page_number,
                section_heading=r.section_heading, document_title=r.document_title,
                source_filename=r.source_filename, token_set=frozenset(tokenize(r.text)),
            )
            for r in records
        ]
        if self._chunks:
            # Full token list WITH repeats — BM25 term-frequency depends on
            # repeat counts; token_set (deduped) is only for the overlap
            # filter in search(), never for indexing.
            tokenized_corpus = [tokenize(c.text) for c in self._chunks]
            self._bm25 = BM25Okapi(tokenized_corpus)
        else:
            self._bm25 = None
        logger.info("bm25_index_refreshed", extra={"event_data": {"chunk_count": len(self._chunks)}})

    def search(self, query_text: str, top_k: int) -> list[SparseHit]:
        if self._bm25 is None or not self._chunks:
            return []

        query_tokens = tokenize(query_text)
        query_token_set = frozenset(query_tokens)
        scores = self._bm25.get_scores(query_tokens)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        hits: list[SparseHit] = []
        for rank, idx in enumerate(ranked_indices, start=1):
            chunk = self._chunks[idx]
            # Inclusion decided by genuine token overlap, NOT by the BM25
            # score's sign — classic Okapi IDF can legitimately score a
            # real match as exactly 0.0 in a small corpus (see architecture
            # docs for the confirmed 2-document repro of this).
            if not (query_token_set & chunk.token_set):
                continue
            hits.append(
                SparseHit(
                    chunk_id=chunk.chunk_id, document_id=chunk.document_id, text=chunk.text,
                    bm25_score=float(scores[idx]), sparse_rank=rank, page_number=chunk.page_number,
                    section_heading=chunk.section_heading, document_title=chunk.document_title,
                    source_filename=chunk.source_filename,
                )
            )
        return hits


bm25_store = BM25Store()
