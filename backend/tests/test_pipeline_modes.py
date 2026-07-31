import uuid

from app.ingestion.chunker import ChunkingStrategy
from app.models.database import ChunkRecord, SessionLocal, init_db
from app.retrieval import dense
from app.retrieval.sparse import bm25_store
from app.services.pipeline import RetrievalMode, run_retrieval


def _make_chunk(chunk_id, document_id, text, source_filename="test.pdf"):
    return ChunkRecord(
        chunk_id=chunk_id, document_id=document_id, source_filename=source_filename, document_title="Test Doc",
        page_number=1, section_heading="Results", chunk_index=0, text=text, character_count=len(text),
        token_count=len(text.split()), chunking_strategy=ChunkingStrategy.RECURSIVE_FIXED.value,
    )


def _setup_chunks():
    document_id = f"doc_{uuid.uuid4().hex[:8]}"
    filename = f"{document_id}.pdf"
    chunks = [
        _make_chunk(f"{document_id}_c1", document_id, "IL-6 biomarker levels rose in treated patients", filename),
        _make_chunk(f"{document_id}_c2", document_id, "completely unrelated text about cooking recipes", filename),
    ]
    dense.add_chunks(chunks)

    init_db()
    db = SessionLocal()
    for c in chunks:
        db.add(c)
    db.commit()
    bm25_store.refresh(db)
    return document_id, chunks, db


def _teardown_chunks(document_id, db):
    db.query(ChunkRecord).filter(ChunkRecord.document_id == document_id).delete()
    db.commit()
    dense.delete_document(document_id)
    bm25_store.refresh(db)
    db.close()


def test_dense_only_mode_skips_sparse_retrieval():
    document_id, chunks, db = _setup_chunks()
    try:
        result = run_retrieval("IL-6 biomarker levels", db, mode=RetrievalMode.DENSE_ONLY, top_k=5)
        assert len(result.dense_hits) > 0
        assert result.sparse_hits == []
        assert result.fused_hits == []
        assert len(result.hits) > 0
        assert result.hits[0].dense_rank is not None
        assert result.hits[0].sparse_rank is None
        assert result.hits[0].rrf_rank is None
    finally:
        _teardown_chunks(document_id, db)


def test_sparse_only_mode_skips_dense_retrieval():
    document_id, chunks, db = _setup_chunks()
    try:
        result = run_retrieval("IL-6 biomarker levels", db, mode=RetrievalMode.SPARSE_ONLY, top_k=5)
        assert result.dense_hits == []
        assert len(result.sparse_hits) > 0
        assert result.fused_hits == []
        assert len(result.hits) > 0
        assert result.hits[0].sparse_rank is not None
        assert result.hits[0].dense_rank is None
    finally:
        _teardown_chunks(document_id, db)


def test_hybrid_rrf_mode_runs_both_but_no_reranker():
    document_id, chunks, db = _setup_chunks()
    try:
        result = run_retrieval("IL-6 biomarker levels", db, mode=RetrievalMode.HYBRID_RRF, top_k=5)
        assert len(result.dense_hits) > 0
        assert len(result.sparse_hits) > 0
        assert len(result.fused_hits) > 0
        assert len(result.hits) > 0
        assert result.hits[0].rrf_rank is not None
    finally:
        _teardown_chunks(document_id, db)


def test_hybrid_rrf_rerank_mode_is_the_full_production_pipeline():
    document_id, chunks, db = _setup_chunks()
    try:
        result = run_retrieval("IL-6 biomarker levels", db, mode=RetrievalMode.HYBRID_RRF_RERANK, top_k=5)
        assert len(result.fused_hits) > 0
        assert len(result.hits) > 0
        assert isinstance(result.hits[0].reranker_score, float)
        assert result.hits[0].final_rank == 1
    finally:
        _teardown_chunks(document_id, db)


def test_all_modes_return_uniform_hit_shape():
    document_id, chunks, db = _setup_chunks()
    try:
        for mode in RetrievalMode:
            result = run_retrieval("IL-6 biomarker levels", db, mode=mode, top_k=5)
            for hit in result.hits:
                assert hasattr(hit, "chunk_id")
                assert hasattr(hit, "reranker_score")
                assert hasattr(hit, "final_rank")
                assert hasattr(hit, "source_filename")
    finally:
        _teardown_chunks(document_id, db)
