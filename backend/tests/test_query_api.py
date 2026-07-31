import io
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models.database import init_db

init_db()
client = TestClient(app)


def test_query_full_pipeline_returns_grounded_cited_answer():
    unique_marker = uuid.uuid4().hex[:12]
    content = (
        f"Abstract\nThis study examines biomarker {unique_marker} in patients with elevated IL-6 levels.\n\n"
        f"Results\nBiomarker {unique_marker} was significantly associated with treatment response.\n"
    ).encode()
    files = {"file": (f"study_{unique_marker}.txt", io.BytesIO(content), "text/plain")}
    upload_resp = client.post("/api/v1/documents/upload", files=files)
    document_id = upload_resp.json()["document_id"]

    resp = client.post("/api/v1/query", json={"question": f"What is known about biomarker {unique_marker}?"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["answer"]
    assert isinstance(body["claims"], list)
    assert len(body["claims"]) >= 1
    for claim in body["claims"]:
        assert "claim_id" in claim and "claim_text" in claim
    assert body["confidence"] is not None
    assert 0.0 <= body["confidence"] <= 100.0
    assert body["confidence_label"] in ("High", "Moderate", "Low")
    assert body["confidence_breakdown"] is not None

    assert body["retrieval_debug"] is None
    assert set(body["processing_latency_ms"].keys()) >= {
        "dense_ms", "sparse_ms", "rrf_ms", "rerank_ms", "generation_ms", "verification_ms", "total_ms",
    }

    client.delete(f"/api/v1/documents/{document_id}")


def test_query_with_retrieval_debug_includes_reranked_results():
    unique_marker = uuid.uuid4().hex[:12]
    content = f"Abstract\nBiomarker {unique_marker} was elevated in the treatment arm.\n".encode()
    files = {"file": (f"debug_{unique_marker}.txt", io.BytesIO(content), "text/plain")}
    upload_resp = client.post("/api/v1/documents/upload", files=files)
    document_id = upload_resp.json()["document_id"]

    resp = client.post(
        "/api/v1/query",
        json={"question": f"What about biomarker {unique_marker}?", "include_retrieval_debug": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["retrieval_debug"] is not None
    assert body["retrieval_debug"]["reranked_results"] is not None

    client.delete(f"/api/v1/documents/{document_id}")


def test_query_respects_top_k_override():
    resp = client.post("/api/v1/query", json={"question": "gene expression", "top_k": 1})
    assert resp.status_code == 200


def test_query_persists_to_query_history_and_claims_tables():
    from app.models.database import ClaimRecord, QueryHistoryRecord, SessionLocal

    unique_marker = uuid.uuid4().hex[:12]
    content = f"Abstract\nA persistence test document about marker {unique_marker} and its clinical role.\n".encode()
    files = {"file": (f"persist_{unique_marker}.txt", io.BytesIO(content), "text/plain")}
    upload_resp = client.post("/api/v1/documents/upload", files=files)
    document_id = upload_resp.json()["document_id"]

    query_resp = client.post("/api/v1/query", json={"question": f"What is marker {unique_marker}?"})
    assert query_resp.status_code == 200
    body = query_resp.json()

    db = SessionLocal()
    try:
        history_rows = db.query(QueryHistoryRecord).filter(
            QueryHistoryRecord.question == f"What is marker {unique_marker}?"
        ).all()
        assert len(history_rows) == 1
        assert history_rows[0].confidence_score == body["confidence"]

        if body["claims"]:
            claim_rows = db.query(ClaimRecord).filter(ClaimRecord.query_id == history_rows[0].query_id).all()
            assert len(claim_rows) == len(body["claims"])
    finally:
        db.close()

    client.delete(f"/api/v1/documents/{document_id}")


def test_regression_fullwidth_citations_do_not_collapse_confidence(monkeypatch):
    """
    Reproduces the real bug chain end-to-end through the live endpoint: an
    LLM response using fullwidth-bracket citations must still produce
    non-empty citations, claims with populated citation_numbers, a
    non-zero retrieval_confidence, and a final confidence that reflects
    genuinely well-supported evidence — not the all-zeros cascade this bug
    previously produced.
    """
    import app.generation.generator as generator_module
    from app.generation.llm import LLMResponse

    unique_marker = uuid.uuid4().hex[:12]
    content = (
        f"Abstract\nBiomarker {unique_marker} was strongly elevated in treated patients "
        f"and closely tracked clinical improvement across the cohort.\n"
    ).encode()
    files = {"file": (f"regression_{unique_marker}.txt", io.BytesIO(content), "text/plain")}
    upload_resp = client.post("/api/v1/documents/upload", files=files)
    document_id = upload_resp.json()["document_id"]

    def fullwidth_bracket_llm(prompt, system_prompt=None):
        return LLMResponse(
            text=f"Biomarker {unique_marker} was strongly elevated in treated patients \u30101\u3011.",
            model="fake-fullwidth",
        )

    monkeypatch.setattr(generator_module, "llm_generate", fullwidth_bracket_llm)

    query_resp = client.post("/api/v1/query", json={"question": f"What was observed for biomarker {unique_marker}?"})
    assert query_resp.status_code == 200
    body = query_resp.json()

    assert len(body["citations"]) >= 1
    assert len(body["claims"]) >= 1
    assert any(c["citation_numbers"] for c in body["claims"])
    assert any(c["verification_label"] is not None for c in body["claims"])
    assert body["confidence_breakdown"]["retrieval_confidence"] > 0.0
    assert body["confidence"] > 10.0
    assert body["confidence_label"] != "Low"
    assert body["insufficient_evidence"] is False

    client.delete(f"/api/v1/documents/{document_id}")
