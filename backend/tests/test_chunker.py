from app.ingestion.chunker import chunk_document, recursive_fixed_chunk
from app.ingestion.parser import PageContent, ParsedDocument
from app.models.schemas import ChunkingStrategy

SAMPLE_PAPER_TEXT = """A Study of Something Interesting

Abstract
This is the abstract of the paper describing background and results in brief detail.

Introduction
This section introduces the problem being studied and prior work in the field.

Methods
This section describes the methods used including materials and procedures employed.

Results
This section presents the results found during the experiments that were conducted.

Discussion
This section discusses the implications of the results found during the study.

References
1. Some Author, Some Journal, 2020.
"""


def _parsed(text):
    return ParsedDocument(
        source_filename="sample.txt", full_text=text,
        pages=[PageContent(page_number=None, text=text, char_start=0)],
        detected_title="A Study of Something Interesting", page_count=None,
    )


def test_structure_aware_chunk_detects_scientific_sections():
    parsed = _parsed(SAMPLE_PAPER_TEXT)
    chunks = chunk_document(parsed, ChunkingStrategy.STRUCTURE_AWARE)
    headings = {c.section_heading for c in chunks}
    for expected in ["Abstract", "Introduction", "Methods", "Results", "Discussion", "References"]:
        assert expected in headings
    for c in chunks:
        assert c.chunking_strategy == ChunkingStrategy.STRUCTURE_AWARE.value


def test_structure_aware_chunk_includes_preamble():
    parsed = _parsed(SAMPLE_PAPER_TEXT)
    chunks = chunk_document(parsed, ChunkingStrategy.STRUCTURE_AWARE)
    assert chunks[0].section_heading == "Preamble"
    assert "A Study of Something Interesting" in chunks[0].text


def test_structure_aware_falls_back_to_recursive_when_no_headings_found():
    plain_text = "Just a plain paragraph of text with no section headings at all. " * 20
    parsed = _parsed(plain_text)
    chunks = chunk_document(parsed, ChunkingStrategy.STRUCTURE_AWARE)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.chunking_strategy == ChunkingStrategy.RECURSIVE_FIXED.value
        assert c.section_heading is None


def test_recursive_fixed_chunk_respects_size_and_overlap(monkeypatch):
    from app.core import config as config_module
    monkeypatch.setattr(config_module.settings, "chunk_size", 200)
    monkeypatch.setattr(config_module.settings, "chunk_overlap", 50)
    long_text = ("Sentence about biomarkers and gene expression. " * 60).strip()
    parsed = _parsed(long_text)
    chunks = recursive_fixed_chunk(parsed)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= 200 + 100
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_recursive_fixed_chunk_produces_single_chunk_for_short_text():
    parsed = _parsed("A short document.")
    chunks = recursive_fixed_chunk(parsed)
    assert len(chunks) == 1
    assert chunks[0].text == "A short document."
