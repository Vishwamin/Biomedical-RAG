"""
Document parsing: PDF / TXT / MD -> normalized text with page tracking.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

from app.core.exceptions import UnsupportedFileTypeError, IngestionError

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


@dataclass
class PageContent:
    page_number: int | None
    text: str
    char_start: int


@dataclass
class ParsedDocument:
    source_filename: str
    full_text: str
    pages: list[PageContent] = field(default_factory=list)
    detected_title: str | None = None
    page_count: int | None = None


_BARE_PAGE_NUMBER = re.compile(r"^\d{1,4}$")
_PAGE_X_OF_Y = re.compile(r"^page\s*\d+(\s*(of|/)\s*\d+)?$", re.IGNORECASE)


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_extraction_artifacts(text: str) -> str:
    kept_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if _BARE_PAGE_NUMBER.match(stripped) or _PAGE_X_OF_Y.match(stripped):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def _clean(raw_text: str) -> str:
    return _strip_extraction_artifacts(_normalize_whitespace(raw_text))


def _detect_pdf_title(doc, pages: list[PageContent]) -> str | None:
    meta_title = (doc.metadata or {}).get("title")
    if meta_title and meta_title.strip() and not meta_title.lower().endswith(".pdf"):
        return meta_title.strip()

    if pages:
        candidates = [l.strip() for l in pages[0].text.split("\n") if l.strip()]
        for line in candidates[:6]:
            if 15 <= len(line) <= 200 and line.lower() not in ("abstract",):
                return line
    return None


def parse_pdf(file_path: Path) -> ParsedDocument:
    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        raise IngestionError(f"Could not open PDF: {exc}", details={"filename": file_path.name}) from exc

    pages: list[PageContent] = []
    full_text_parts: list[str] = []
    char_offset = 0

    for i, page in enumerate(doc, start=1):
        cleaned = _clean(page.get_text("text"))
        if cleaned:
            pages.append(PageContent(page_number=i, text=cleaned, char_start=char_offset))
            full_text_parts.append(cleaned)
            char_offset += len(cleaned) + 2

    full_text = "\n\n".join(full_text_parts)
    title = _detect_pdf_title(doc, pages)
    page_count = doc.page_count
    doc.close()

    if not full_text.strip():
        raise IngestionError(
            "PDF produced no extractable text (likely a scanned/image-only PDF; OCR is not yet supported).",
            details={"filename": file_path.name},
        )

    return ParsedDocument(
        source_filename=file_path.name,
        full_text=full_text,
        pages=pages,
        detected_title=title,
        page_count=page_count,
    )


def parse_text_file(file_path: Path) -> ParsedDocument:
    raw = file_path.read_text(encoding="utf-8", errors="ignore")
    cleaned = _clean(raw)

    if not cleaned.strip():
        raise IngestionError("File is empty after cleaning.", details={"filename": file_path.name})

    lines = [l.strip() for l in cleaned.split("\n") if l.strip()]
    title = None
    if lines:
        first = lines[0].lstrip("#").strip()
        if 5 <= len(first) <= 200:
            title = first
    if title is None:
        title = file_path.stem

    pages = [PageContent(page_number=None, text=cleaned, char_start=0)]
    return ParsedDocument(
        source_filename=file_path.name, full_text=cleaned, pages=pages, detected_title=title, page_count=None
    )


def parse_document(file_path: Path) -> ParsedDocument:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(file_path)
    if suffix in (".txt", ".md"):
        return parse_text_file(file_path)
    raise UnsupportedFileTypeError(
        f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        details={"filename": file_path.name},
    )
