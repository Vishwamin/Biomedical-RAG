from app.retrieval.reranker import RerankedHit, rerank
from app.retrieval.rrf import FusedHit


def _fused(chunk_id, rrf_score, rank):
    return FusedHit(
        chunk_id=chunk_id, document_id="docA", text=f"passage {chunk_id}", dense_rank=1, dense_score=0.8,
        sparse_rank=1, bm25_score=3.0, rrf_score=rrf_score, fused_rank=rank, page_number=1,
        section_heading="Results", document_title="Doc", source_filename="doc.pdf",
    )


def test_rerank_reorders_by_score_fn():
    candidates = [_fused("low", 0.02, 1), _fused("high", 0.01, 2)]

    def fake_score_fn(query, passages):
        return [0.1 if "low" in p else 0.9 for p in passages]

    results = rerank("query", candidates, top_k=2, score_fn=fake_score_fn)
    assert results[0].chunk_id == "high"
    assert results[0].final_rank == 1
    assert results[1].chunk_id == "low"


def test_rerank_preserves_full_provenance():
    candidates = [_fused("c1", 0.02, 1)]
    results = rerank("query", candidates, top_k=1, score_fn=lambda q, p: [0.5])
    hit = results[0]
    assert hit.dense_rank == 1
    assert hit.sparse_rank == 1
    assert hit.rrf_rank == 1
    assert hit.reranker_score == 0.5


def test_rerank_respects_top_k():
    candidates = [_fused(f"c{i}", 0.01 * i, i) for i in range(1, 6)]
    results = rerank("query", candidates, top_k=2, score_fn=lambda q, p: [1.0] * len(p))
    assert len(results) == 2


def test_rerank_empty_candidates_returns_empty_list():
    assert rerank("query", [], top_k=5) == []
