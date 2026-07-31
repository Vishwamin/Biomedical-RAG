"""
Dense semantic retrieval via ChromaDB.
"""

from dataclasses import dataclass

import chromadb

from app.core.config import settings
from app.embeddings.embedder import embed_query, embed_texts
from app.models.database import ChunkRecord

_client = None


def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_directory)
    return _client


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_name, metadata={"hnsw:space": "cosine"}
    )


def reset_client() -> None:
    global _client
    _client = None


@dataclass
class DenseHit:
    chunk_id: str
    document_id: str
    text: str
    dense_score: float
    dense_rank: int
    page_number: int | None
    section_heading: str | None
    document_title: str | None
    source_filename: str


def _chunk_metadata(chunk: ChunkRecord) -> dict:
    return {
        "document_id": chunk.document_id,
        "page_number": chunk.page_number if chunk.page_number is not None else -1,
        "section_heading": chunk.section_heading or "",
        "document_title": chunk.document_title or "",
        "source_filename": chunk.source_filename,
        "chunk_index": chunk.chunk_index,
    }


def add_chunks(chunks: list[ChunkRecord], embed_fn=None) -> None:
    if not chunks:
        return
    embed_fn = embed_fn or embed_texts
    texts = [c.text for c in chunks]
    vectors = embed_fn(texts)
    collection = get_collection()
    collection.upsert(
        ids=[c.chunk_id for c in chunks], embeddings=vectors, documents=texts,
        metadatas=[_chunk_metadata(c) for c in chunks],
    )


def delete_document(document_id: str) -> None:
    collection = get_collection()
    collection.delete(where={"document_id": document_id})


def search(query_text: str, top_k: int, embed_fn=None) -> list[DenseHit]:
    embed_fn = embed_fn or embed_query
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []

    query_vector = embed_fn(query_text)
    results = collection.query(query_embeddings=[query_vector], n_results=min(top_k, count))

    hits: list[DenseHit] = []
    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for rank, (chunk_id, text, meta, distance) in enumerate(zip(ids, documents, metadatas, distances), start=1):
        similarity = 1.0 - distance
        hits.append(
            DenseHit(
                chunk_id=chunk_id, document_id=meta.get("document_id"), text=text, dense_score=similarity,
                dense_rank=rank, page_number=None if meta.get("page_number") == -1 else meta.get("page_number"),
                section_heading=meta.get("section_heading") or None, source_filename=meta.get("source_filename"),
                document_title=meta.get("document_title") or None,
            )
        )
    return hits
