from app.retrieval.dense import DenseHit
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.sparse import SparseHit


def _dense(chunk_id, rank, score=0.9, document_id="docA"):
    return DenseHit(
        chunk_id=chunk_id, document_id=document_id, text=f"text for {chunk_id}", dense_score=score,
        dense_rank=rank, page_number=1, section_heading="Results", document_title="Doc", source_filename="doc.pdf",
    )


def _sparse(chunk_id, rank, score=5.0, document_id="docA"):
    return SparseHit(
        chunk_id=chunk_id, document_id=document_id, text=f"text for {chunk_id}", bm25_score=score,
        sparse_rank=rank, page_number=1, section_heading="Results", document_title="Doc", source_filename="doc.pdf",
    )


def test_rrf_boosts_chunk_found_by_both_retrievers():
    dense_hits = [_dense("c1", 1), _dense("c2", 2), _dense("c3", 3)]
    sparse_hits = [_sparse("c2", 1), _sparse("c4", 2)]
    fused = reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
    fused_by_id = {f.chunk_id: f for f in fused}
    assert fused_by_id["c2"].rrf_score > fused_by_id["c1"].rrf_score
    assert fused[0].chunk_id == "c2"
    assert fused[0].fused_rank == 1


def test_rrf_preserves_original_ranks_and_scores():
    dense_hits = [_dense("c1", 1, score=0.95)]
    sparse_hits = [_sparse("c1", 1, score=8.2)]
    fused = reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
    assert len(fused) == 1
    hit = fused[0]
    assert hit.dense_rank == 1
    assert hit.dense_score == 0.95
    assert hit.sparse_rank == 1
    assert hit.bm25_score == 8.2
    expected_score = (1.0 / (60 + 1)) + (1.0 / (60 + 1))
    assert abs(hit.rrf_score - expected_score) < 1e-9


def test_rrf_handles_dense_only_and_sparse_only_chunks():
    dense_hits = [_dense("dense_only", 1)]
    sparse_hits = [_sparse("sparse_only", 1)]
    fused = reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
    fused_by_id = {f.chunk_id: f for f in fused}
    assert fused_by_id["dense_only"].sparse_rank is None
    assert fused_by_id["dense_only"].bm25_score is None
    assert fused_by_id["sparse_only"].dense_rank is None
    assert fused_by_id["sparse_only"].dense_score is None


def test_rrf_respects_weighting():
    dense_hits = [_dense("c1", 1)]
    sparse_hits = [_sparse("c1", 1)]
    unweighted = reciprocal_rank_fusion(dense_hits, sparse_hits, k=60, dense_weight=1.0, sparse_weight=1.0)
    dense_favored = reciprocal_rank_fusion(dense_hits, sparse_hits, k=60, dense_weight=5.0, sparse_weight=1.0)
    assert dense_favored[0].rrf_score > unweighted[0].rrf_score


def test_rrf_empty_inputs_returns_empty_list():
    assert reciprocal_rank_fusion([], []) == []
