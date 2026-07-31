from app.ingestion.chunker import ChunkingStrategy
from app.models.database import ChunkRecord, SessionLocal, init_db
from app.retrieval.sparse import BM25Store, tokenize


def test_tokenize_preserves_hyphenated_biomedical_terms():
    tokens = tokenize("Elevated IL-6 and PD-L1 expression was observed in TP53-mutant cells.")
    assert "il-6" in tokens
    assert "pd-l1" in tokens
    assert "tp53-mutant" in tokens


def test_tokenize_lowercases_and_splits_on_whitespace():
    tokens = tokenize("Gene Expression Analysis")
    assert tokens == ["gene", "expression", "analysis"]


def _make_chunk(chunk_id, document_id, text, chunk_index=0):
    return ChunkRecord(
        chunk_id=chunk_id, document_id=document_id, source_filename="test.txt", document_title="Test Doc",
        page_number=None, section_heading=None, chunk_index=chunk_index, text=text, character_count=len(text),
        token_count=len(text.split()), chunking_strategy=ChunkingStrategy.RECURSIVE_FIXED.value,
    )


def test_bm25_store_ranks_exact_term_match_higher():
    init_db()
    db = SessionLocal()
    try:
        db.query(ChunkRecord).delete()
        db.commit()
        chunks = [
            _make_chunk("c1", "docA", "This chunk discusses IL-6 biomarkers in inflammatory disease."),
            _make_chunk("c2", "docA", "This chunk is about unrelated topics like cooking recipes."),
            _make_chunk("c3", "docA", "Another chunk mentioning gene expression but not the specific marker."),
        ]
        for c in chunks:
            db.add(c)
        db.commit()

        store = BM25Store()
        store.refresh(db)
        results = store.search("IL-6 biomarkers", top_k=5)

        assert len(results) >= 1
        assert results[0].chunk_id == "c1"
        assert results[0].sparse_rank == 1
        assert results[0].bm25_score > 0

        db.query(ChunkRecord).delete()
        db.commit()
    finally:
        db.close()


def test_bm25_store_returns_empty_when_not_built():
    store = BM25Store()
    assert store.is_built is False
    assert store.search("anything", top_k=5) == []


def test_regression_small_corpus_zero_bm25_score_still_counts_as_a_match():
    """
    rank_bm25's classic Okapi IDF (no smoothing) can legitimately score a
    genuinely relevant document as exactly 0.0 whenever a small corpus
    causes a query term to appear in about half the indexed chunks — a
    2-document corpus where the matching term appears in exactly 1 of 2
    documents triggers this precisely. Inclusion is decided by genuine
    token overlap, not by the BM25 score's sign.
    """
    init_db()
    db = SessionLocal()
    try:
        db.query(ChunkRecord).delete()
        db.commit()

        matching = _make_chunk("c1", "docA", "IL-6 biomarker levels rose in treated patients")
        unrelated = _make_chunk("c2", "docA", "completely unrelated text about cooking recipes")
        db.add(matching)
        db.add(unrelated)
        db.commit()

        store = BM25Store()
        store.refresh(db)
        results = store.search("IL-6 biomarker levels", top_k=5)

        assert any(r.chunk_id == "c1" for r in results)

        db.query(ChunkRecord).delete()
        db.commit()
    finally:
        db.close()
