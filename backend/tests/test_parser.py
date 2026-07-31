import fitz
import pytest

from app.core.exceptions import IngestionError, UnsupportedFileTypeError
from app.ingestion.parser import parse_document, parse_pdf, parse_text_file


def _make_pdf(tmp_path, pages_text):
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(72, 72, 500, 700), text)
    path = tmp_path / "sample.pdf"
    doc.save(str(path))
    doc.close()
    return path


def test_parse_pdf_extracts_pages_and_tracks_offsets(tmp_path):
    path = _make_pdf(tmp_path, ["This is page one content about proteins.", "This is page two content about genes."])
    parsed = parse_pdf(path)
    assert parsed.page_count == 2
    assert len(parsed.pages) == 2
    assert "proteins" in parsed.full_text
    assert "genes" in parsed.full_text
    assert parsed.pages[1].char_start > 0


def test_parse_pdf_empty_raises_ingestion_error(tmp_path):
    doc = fitz.open()
    doc.new_page()
    path = tmp_path / "blank.pdf"
    doc.save(str(path))
    doc.close()
    with pytest.raises(IngestionError):
        parse_pdf(path)


def test_parse_text_file_strips_page_number_artifacts(tmp_path):
    content = "Introduction\nSome real content line.\n42\nPage 3 of 10\nMore real content."
    path = tmp_path / "notes.txt"
    path.write_text(content)
    parsed = parse_text_file(path)
    assert "Some real content line." in parsed.full_text
    assert "More real content." in parsed.full_text
    assert "42" not in parsed.full_text.split("\n")
    assert "Page 3 of 10" not in parsed.full_text


def test_parse_text_file_detects_title_from_first_line(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("# A Study of Something Interesting\n\nBody text goes here.")
    parsed = parse_text_file(path)
    assert parsed.detected_title == "A Study of Something Interesting"


def test_parse_document_rejects_unsupported_extension(tmp_path):
    path = tmp_path / "image.png"
    path.write_bytes(b"\x89PNG\r\n")
    with pytest.raises(UnsupportedFileTypeError):
        parse_document(path)
