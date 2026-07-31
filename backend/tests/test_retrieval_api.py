import io
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models.database import init_db

init_db()
client = TestClient(app)


def test_retrieve_returns_dense_sparse_and_fused_results():
    unique_marker = uuid.uuid4().hex[:12]
    content = (
        f"Abstract\nThis study examines biomarker {unique_marker} in patients with elevated IL-6 levels.\n\n"
        f"Methods\nWe measured gene expression using RNA sequencing across cohorts.\n\n"
        f"Results\nBiomarker {unique_marker} was significantly associated with treatment response.\n"
    ).encode()

    files = {"file": (f"study_{unique_marker}.txt", io.BytesIO(content), "text/plain")}
    upload_resp = client.post("/api/v1/documents/upload", files=files)
    assert upload_resp.status_code == 201
    doc = upload_resp.json()
    assert doc["status"] == "indexed"
    document_id = doc["document_id"]

    retrieve_resp = client.post("/api/v1/retrieve", json={"question": f"What is known about biomarker {unique_marker}?"})
    assert retrieve_resp.status_code == 200
    body = retrieve_resp.json()

    assert len(body["dense_results"]) >= 1
    assert len(body["sparse_results"]) >= 1
    assert len(body["fused_results"]) >= 1
    assert body["reranked_results"] is None

    fused_chunk_ids = {r["chunk_id"] for r in body["fused_results"]}
    doc_chunk_ids = {c["chunk_id"] for c in client.get(f"/api/v1/documents/{document_id}/chunks").json()}
    assert fused_chunk_ids & doc_chunk_ids

    for r in body["fused_results"]:
        assert r["rrf_score"] > 0
        assert r["fused_rank"] >= 1

    client.delete(f"/api/v1/documents/{document_id}")


def test_retrieve_with_no_documents_returns_empty_lists():
    resp = client.post("/api/v1/retrieve", json={"question": "zzzznonexistentqueryterm12345"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["dense_results"], list)
    assert isinstance(body["sparse_results"], list)
    assert isinstance(body["fused_results"], list)


def test_retrieve_respects_top_k_override():
    resp = client.post("/api/v1/retrieve", json={"question": "gene expression", "dense_top_k": 2, "sparse_top_k": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["dense_results"]) <= 2
    assert len(body["sparse_results"]) <= 2
