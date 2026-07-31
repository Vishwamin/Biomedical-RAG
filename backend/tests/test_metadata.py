from app.ingestion.metadata import compute_content_hash, generate_chunk_id, generate_document_id


def test_compute_content_hash_is_deterministic():
    data = b"some file bytes"
    assert compute_content_hash(data) == compute_content_hash(data)


def test_compute_content_hash_differs_for_different_content():
    assert compute_content_hash(b"content a") != compute_content_hash(b"content b")


def test_generate_document_id_format_and_uniqueness():
    a = generate_document_id()
    b = generate_document_id()
    assert a != b
    assert a.startswith("doc_")
    assert len(a) == len("doc_") + 12


def test_generate_chunk_id_format():
    chunk_id = generate_chunk_id("doc_abc123", 7)
    assert chunk_id == "doc_abc123_chunk_0007"
