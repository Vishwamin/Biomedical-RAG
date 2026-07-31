import io
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models.database import init_db

init_db()
client = TestClient(app)


def _upload_test_doc():
    marker = uuid.uuid4().hex[:10]
    content = f"Abstract\nBiomarker {marker} was elevated in treated patients and tracked with clinical response.\n".encode()
    files = {"file": (f"chat_test_{marker}.txt", io.BytesIO(content), "text/plain")}
    resp = client.post("/api/v1/documents/upload", files=files)
    return resp.json()["document_id"], marker


def test_create_list_get_delete_chat_roundtrip():
    create_resp = client.post("/api/v1/chats", json={})
    assert create_resp.status_code == 201
    chat = create_resp.json()
    assert chat["title"] == "New Chat"
    assert chat["pinned"] is False
    chat_id = chat["id"]

    list_resp = client.get("/api/v1/chats")
    assert list_resp.status_code == 200
    assert any(c["id"] == chat_id for c in list_resp.json())

    get_resp = client.get(f"/api/v1/chats/{chat_id}")
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["id"] == chat_id
    assert detail["messages"] == []

    delete_resp = client.delete(f"/api/v1/chats/{chat_id}")
    assert delete_resp.status_code == 200

    get_after_delete = client.get(f"/api/v1/chats/{chat_id}")
    assert get_after_delete.status_code == 404
    assert get_after_delete.json()["error"] == "chat_not_found"


def test_new_chat_does_not_delete_other_chats():
    first = client.post("/api/v1/chats", json={}).json()
    second = client.post("/api/v1/chats", json={}).json()

    chat_ids = {c["id"] for c in client.get("/api/v1/chats").json()}
    assert first["id"] in chat_ids
    assert second["id"] in chat_ids

    client.delete(f"/api/v1/chats/{first['id']}")
    client.delete(f"/api/v1/chats/{second['id']}")


def test_send_message_persists_full_response_and_auto_titles_chat():
    document_id, marker = _upload_test_doc()
    chat = client.post("/api/v1/chats", json={}).json()
    chat_id = chat["id"]

    resp = client.post(
        f"/api/v1/chats/{chat_id}/messages",
        json={"content": f"What was observed for biomarker {marker}?"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["content"]
    assert body["chat"]["title"] != "New Chat"  # auto-titled from first message

    # confirm it's actually persisted, not just returned once
    detail = client.get(f"/api/v1/chats/{chat_id}").json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][1]["role"] == "assistant"
    assert detail["title"] == body["chat"]["title"]

    client.delete(f"/api/v1/chats/{chat_id}")
    client.delete(f"/api/v1/documents/{document_id}")


def test_second_message_does_not_change_title():
    document_id, marker = _upload_test_doc()
    chat = client.post("/api/v1/chats", json={}).json()
    chat_id = chat["id"]

    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": f"What about biomarker {marker}?"})
    title_after_first = client.get(f"/api/v1/chats/{chat_id}").json()["title"]

    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "Why?"})
    title_after_second = client.get(f"/api/v1/chats/{chat_id}").json()["title"]

    assert title_after_first == title_after_second

    client.delete(f"/api/v1/chats/{chat_id}")
    client.delete(f"/api/v1/documents/{document_id}")


def test_reopening_a_chat_returns_persisted_data_without_rerunning(monkeypatch):
    """
    Confirms opening an existing chat is a pure read: patch the pipeline
    to explode if called, then verify GET /chats/{id} still succeeds and
    returns the exact same message content as when it was created.
    """
    document_id, marker = _upload_test_doc()
    chat = client.post("/api/v1/chats", json={}).json()
    chat_id = chat["id"]

    send_resp = client.post(
        f"/api/v1/chats/{chat_id}/messages", json={"content": f"What about biomarker {marker}?"}
    )
    original_answer = send_resp.json()["assistant_message"]["content"]
    original_confidence = send_resp.json()["assistant_message"]["confidence"]

    import app.services.chat_service as chat_service_module

    def explode(*args, **kwargs):
        raise AssertionError("Reopening a chat must not rerun the RAG pipeline")

    monkeypatch.setattr(chat_service_module, "execute_rag_query", explode)

    detail = client.get(f"/api/v1/chats/{chat_id}").json()
    assistant_msg = detail["messages"][1]
    assert assistant_msg["content"] == original_answer
    assert assistant_msg["confidence"] == original_confidence
    assert assistant_msg["citations"] is not None
    assert assistant_msg["claims"] is not None

    client.delete(f"/api/v1/chats/{chat_id}")
    client.delete(f"/api/v1/documents/{document_id}")


def test_pin_and_unpin_chat():
    chat = client.post("/api/v1/chats", json={}).json()
    chat_id = chat["id"]

    pin_resp = client.patch(f"/api/v1/chats/{chat_id}/pin", json={"pinned": True})
    assert pin_resp.status_code == 200
    assert pin_resp.json()["pinned"] is True

    unpin_resp = client.patch(f"/api/v1/chats/{chat_id}/pin", json={"pinned": False})
    assert unpin_resp.json()["pinned"] is False

    client.delete(f"/api/v1/chats/{chat_id}")


def test_pinned_chats_sort_before_unpinned():
    a = client.post("/api/v1/chats", json={}).json()
    b = client.post("/api/v1/chats", json={}).json()
    client.patch(f"/api/v1/chats/{b['id']}/pin", json={"pinned": True})

    chats = client.get("/api/v1/chats").json()
    ids_in_order = [c["id"] for c in chats]
    assert ids_in_order.index(b["id"]) < ids_in_order.index(a["id"])

    client.delete(f"/api/v1/chats/{a['id']}")
    client.delete(f"/api/v1/chats/{b['id']}")


def test_rename_chat():
    chat = client.post("/api/v1/chats", json={}).json()
    chat_id = chat["id"]

    resp = client.patch(f"/api/v1/chats/{chat_id}", json={"title": "My Renamed Chat"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "My Renamed Chat"

    detail = client.get(f"/api/v1/chats/{chat_id}").json()
    assert detail["title"] == "My Renamed Chat"

    client.delete(f"/api/v1/chats/{chat_id}")


def test_duplicate_chat_copies_messages_independently():
    document_id, marker = _upload_test_doc()
    chat = client.post("/api/v1/chats", json={}).json()
    chat_id = chat["id"]
    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": f"What about biomarker {marker}?"})

    dup_resp = client.post(f"/api/v1/chats/{chat_id}/duplicate")
    assert dup_resp.status_code == 201
    dup = dup_resp.json()
    assert dup["id"] != chat_id
    assert "copy" in dup["title"].lower()

    dup_detail = client.get(f"/api/v1/chats/{dup['id']}").json()
    original_detail = client.get(f"/api/v1/chats/{chat_id}").json()
    assert len(dup_detail["messages"]) == len(original_detail["messages"]) == 2
    assert dup_detail["messages"][0]["id"] != original_detail["messages"][0]["id"]
    assert dup_detail["messages"][0]["content"] == original_detail["messages"][0]["content"]

    # deleting the duplicate must not affect the original
    client.delete(f"/api/v1/chats/{dup['id']}")
    still_there = client.get(f"/api/v1/chats/{chat_id}")
    assert still_there.status_code == 200

    client.delete(f"/api/v1/chats/{chat_id}")
    client.delete(f"/api/v1/documents/{document_id}")


def test_delete_nonexistent_chat_returns_404():
    resp = client.delete("/api/v1/chats/chat_doesnotexist")
    assert resp.status_code == 404
    assert resp.json()["error"] == "chat_not_found"


def test_send_message_to_nonexistent_chat_returns_404():
    resp = client.post("/api/v1/chats/chat_doesnotexist/messages", json={"content": "hello"})
    assert resp.status_code == 404
