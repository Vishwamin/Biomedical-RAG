import io
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models.database import init_db

init_db()
client = TestClient(app)


def _unique_txt_bytes():
    return f"Abstract\nThis is a unique test document {uuid.uuid4().hex}.\n".encode()


def test_upload_list_get_chunks_delete_roundtrip():
    content = _unique_txt_bytes()
    files = {"file": ("test_doc.txt", io.BytesIO(content), "text/plain")}

    upload_resp = client.post("/api/v1/documents/upload", files=files)
    assert upload_resp.status_code == 201
    doc = upload_resp.json()
    document_id = doc["document_id"]
    assert doc["status"] == "indexed"
    assert doc["chunk_count"] >= 1

    list_resp = client.get("/api/v1/documents")
    assert list_resp.status_code == 200
    assert any(d["document_id"] == document_id for d in list_resp.json())

    get_resp = client.get(f"/api/v1/documents/{document_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["document_id"] == document_id

    chunks_resp = client.get(f"/api/v1/documents/{document_id}/chunks")
    assert chunks_resp.status_code == 200
    chunks = chunks_resp.json()
    assert len(chunks) == doc["chunk_count"]
    assert chunks[0]["document_id"] == document_id

    delete_resp = client.delete(f"/api/v1/documents/{document_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "deleted"

    get_after_delete = client.get(f"/api/v1/documents/{document_id}")
    assert get_after_delete.status_code == 404


def test_duplicate_upload_returns_409():
    content = _unique_txt_bytes()
    files = lambda: {"file": ("dup.txt", io.BytesIO(content), "text/plain")}

    first = client.post("/api/v1/documents/upload", files=files())
    assert first.status_code == 201
    document_id = first.json()["document_id"]

    second = client.post("/api/v1/documents/upload", files=files())
    assert second.status_code == 409
    assert second.json()["error"] == "duplicate_document"

    client.delete(f"/api/v1/documents/{document_id}")


def test_unsupported_file_type_returns_400():
    files = {"file": ("image.png", io.BytesIO(b"\x89PNG\r\n"), "image/png")}
    resp = client.post("/api/v1/documents/upload", files=files)
    assert resp.status_code == 400
    assert resp.json()["error"] == "unsupported_file_type"


def test_get_nonexistent_document_returns_404():
    resp = client.get("/api/v1/documents/doc_doesnotexist")
    assert resp.status_code == 404
    assert resp.json()["error"] == "document_not_found"
