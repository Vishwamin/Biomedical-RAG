import uuid

from app.ingestion.chunker import ChunkingStrategy
from app.models.database import ChunkRecord
from app.retrieval import dense


def _make_chunk(chunk_id, document_id, text, page_number=None, section_heading=None):
    return ChunkRecord(
        chunk_id=chunk_id, document_id=document_id, source_filename="test.txt", document_title="Test Doc",
        page_number=page_number, section_heading=section_heading, chunk_index=0, text=text,
        character_count=len(text), token_count=len(text.split()), chunking_strategy=ChunkingStrategy.RECURSIVE_FIXED.value,
    )


def test_add_and_search_returns_relevant_chunk():
    document_id = f"doc_{uuid.uuid4().hex[:8]}"
    chunks = [
        _make_chunk(f"{document_id}_c1", document_id, "gene expression biomarker analysis in tumor cells", page_number=1, section_heading="Results"),
        _make_chunk(f"{document_id}_c2", document_id, "completely unrelated text about weather patterns", page_number=2, section_heading="Discussion"),
    ]
    dense.add_chunks(chunks)
    results = dense.search("gene expression biomarker", top_k=5)
    result_ids = [r.chunk_id for r in results]
    assert f"{document_id}_c1" in result_ids
    top = next(r for r in results if r.chunk_id == f"{document_id}_c1")
    assert top.dense_rank >= 1
    assert 0.0 <= top.dense_score <= 1.0 + 1e-6
    assert top.page_number == 1
    assert top.section_heading == "Results"
    dense.delete_document(document_id)


def test_delete_document_removes_its_chunks():
    document_id = f"doc_{uuid.uuid4().hex[:8]}"
    chunks = [_make_chunk(f"{document_id}_c1", document_id, "some unique searchable content about proteins")]
    dense.add_chunks(chunks)
    before = dense.search("unique searchable content about proteins", top_k=10)
    assert any(r.chunk_id == f"{document_id}_c1" for r in before)
    dense.delete_document(document_id)
    after = dense.search("unique searchable content about proteins", top_k=10)
    assert not any(r.chunk_id == f"{document_id}_c1" for r in after)


def test_search_handles_missing_page_and_section_as_none():
    document_id = f"doc_{uuid.uuid4().hex[:8]}"
    chunks = [_make_chunk(f"{document_id}_c1", document_id, "text with no page or section metadata at all")]
    dense.add_chunks(chunks)
    results = dense.search("text with no page or section metadata", top_k=5)
    hit = next(r for r in results if r.chunk_id == f"{document_id}_c1")
    assert hit.page_number is None
    assert hit.section_heading is None
    dense.delete_document(document_id)


def test_add_chunks_with_empty_list_is_a_noop():
    dense.add_chunks([])
