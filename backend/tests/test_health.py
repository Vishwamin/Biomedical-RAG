from fastapi.testclient import TestClient

from app.main import app
from app.models.database import init_db

init_db()
client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert body["app_name"] == "BioRAG"
    assert body["database_reachable"] is True
    assert "embedding_model" in body
    assert "reranker_model" in body
