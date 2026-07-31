import io
import json
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models.database import init_db

init_db()
client = TestClient(app)


def _write_temp_dataset(tmp_path, filename, unique_marker):
    dataset = {
        "cases": [
            {
                "case_id": f"case_{unique_marker}",
                "question": f"What was observed for biomarker {unique_marker}?",
                "question_type": "direct_factual", "difficulty": "easy", "is_answerable": True,
                "expected_source_filenames": [filename], "expected_answer_summary": None, "notes": "temp test case",
            },
            {
                "case_id": f"case_unanswerable_{unique_marker}",
                "question": f"What dosage of a completely unrelated drug xyz{unique_marker} should be given?",
                "question_type": "insufficient_evidence", "difficulty": "medium", "is_answerable": False,
                "expected_source_filenames": [], "expected_answer_summary": None, "notes": "temp test case",
            },
        ]
    }
    path = tmp_path / "temp_golden_dataset.json"
    path.write_text(json.dumps(dataset))
    return path


def test_evaluation_run_and_read_back_results(tmp_path, monkeypatch):
    import app.evaluation.dataset as dataset_module

    unique_marker = uuid.uuid4().hex[:10]
    filename = f"eval_test_{unique_marker}.txt"
    content = f"Abstract\nBiomarker {unique_marker} was elevated in treated patients and tracked with response.\n".encode()
    files = {"file": (filename, io.BytesIO(content), "text/plain")}
    upload_resp = client.post("/api/v1/documents/upload", files=files)
    assert upload_resp.status_code == 201
    document_id = upload_resp.json()["document_id"]

    temp_dataset_path = _write_temp_dataset(tmp_path, filename, unique_marker)
    monkeypatch.setattr(dataset_module, "DEFAULT_DATASET_PATH", temp_dataset_path)

    run_resp = client.post("/api/v1/evaluation/run", json={})
    assert run_resp.status_code == 200
    body = run_resp.json()

    assert body["dataset_case_count"] == 2
    assert len(body["runs"]) == 1
    run_summary = body["runs"][0]
    assert run_summary["retrieval_mode"] == "hybrid_rrf_rerank"
    assert run_summary["case_count"] == 2

    metrics = run_summary["metrics"]
    for key in ("precision_at_k", "recall_at_k", "mrr", "citation_coverage", "correct_refusal_rate"):
        assert key in metrics

    results_resp = client.get("/api/v1/evaluation/results")
    assert results_resp.status_code == 200
    all_results = results_resp.json()["results"]
    assert any(r["run_id"] == run_summary["run_id"] for r in all_results)

    single_run_resp = client.get(f"/api/v1/evaluation/results/{run_summary['run_id']}")
    assert single_run_resp.status_code == 200
    single_run_results = single_run_resp.json()["results"]
    assert len(single_run_results) == len(metrics)
    assert all(r["run_id"] == run_summary["run_id"] for r in single_run_results)

    client.delete(f"/api/v1/documents/{document_id}")


def test_evaluation_run_with_explicit_ablation_modes(tmp_path, monkeypatch):
    import app.evaluation.dataset as dataset_module

    unique_marker = uuid.uuid4().hex[:10]
    filename = f"eval_ablation_{unique_marker}.txt"
    content = f"Abstract\nMarker {unique_marker} showed a strong correlation with outcome.\n".encode()
    files = {"file": (filename, io.BytesIO(content), "text/plain")}
    upload_resp = client.post("/api/v1/documents/upload", files=files)
    document_id = upload_resp.json()["document_id"]

    temp_dataset_path = _write_temp_dataset(tmp_path, filename, unique_marker)
    monkeypatch.setattr(dataset_module, "DEFAULT_DATASET_PATH", temp_dataset_path)

    run_resp = client.post(
        "/api/v1/evaluation/run",
        json={"modes": ["dense_only", "sparse_only", "hybrid_rrf", "hybrid_rrf_rerank"]},
    )
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert len(body["runs"]) == 4
    modes_returned = {r["retrieval_mode"] for r in body["runs"]}
    assert modes_returned == {"dense_only", "sparse_only", "hybrid_rrf", "hybrid_rrf_rerank"}

    client.delete(f"/api/v1/documents/{document_id}")


def test_evaluation_run_with_no_dataset_returns_clear_error(tmp_path, monkeypatch):
    import app.evaluation.dataset as dataset_module

    monkeypatch.setattr(dataset_module, "DEFAULT_DATASET_PATH", tmp_path / "does_not_exist.json")
    resp = client.post("/api/v1/evaluation/run", json={})
    assert resp.status_code == 500
    assert resp.json()["error"] == "evaluation_failed"
