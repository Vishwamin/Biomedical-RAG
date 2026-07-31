"""
Chunking strategies: recursive fixed-size (baseline) and structure-aware.
"""

import bisect
import re
from dataclasses import dataclass

from app.core.config import settings
from app.ingestion.parser import ParsedDocument, PageContent
from app.models.schemas import ChunkingStrategy


@dataclass
class RawChunk:
    text: str
    chunk_index: int
    page_number: int | None
    section_heading: str | None
    chunking_strategy: str


SECTION_NAMES = [
    "abstract", "introduction", "background", "related work",
    "materials and methods", "methods", "methodology",
    "results and discussion", "results", "discussion",
    "conclusions?", "limitations", "acknowledge?ments?",
    "references", "bibliography", "appendix",
]
_HEADING_REGEX = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s*)?(" + "|".join(SECTION_NAMES) + r")\s*:?$", re.IGNORECASE
)
_MD_HEADING_REGEX = re.compile(r"^#{1,6}\s+(.*\S)\s*$")


def _looks_like_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    md_match = _MD_HEADING_REGEX.match(stripped)
    if md_match:
        return md_match.group(1).strip()[:80]
    if len(stripped) > 60:
        return None
    match = _HEADING_REGEX.match(stripped)
    if match:
        return match.group(1).strip().title()
    return None


def _page_for_offset(pages: list[PageContent], offset: int) -> int | None:
    if not pages or pages[0].page_number is None:
        return None
    starts = [p.char_start for p in pages]
    i = bisect.bisect_right(starts, offset) - 1
    i = max(0, min(i, len(pages) - 1))
    return pages[i].page_number


def _sliding_window(text: str, size: int, overlap: int) -> list[tuple[int, int]]:
    spans = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            lookahead = text[end : end + 100]
            newline_pos = lookahead.find("\n")
            period_pos = lookahead.find(". ")
            extend = -1
            if period_pos != -1 and (newline_pos == -1 or period_pos < newline_pos):
                extend = period_pos + 1
            elif newline_pos != -1:
                extend = newline_pos
            if extend != -1:
                end = min(end + extend + 1, n)
        spans.append((start, end))
        if end >= n:
            break
        start = end - overlap if end - overlap > start else end
    return spans


def recursive_fixed_chunk(parsed: ParsedDocument) -> list[RawChunk]:
    text = parsed.full_text
    chunks: list[RawChunk] = []
    idx = 0
    for start, end in _sliding_window(text, settings.chunk_size, settings.chunk_overlap):
        piece = text[start:end].strip()
        if not piece:
            continue
        chunks.append(
            RawChunk(
                text=piece, chunk_index=idx, page_number=_page_for_offset(parsed.pages, start),
                section_heading=None, chunking_strategy=ChunkingStrategy.RECURSIVE_FIXED.value,
            )
        )
        idx += 1
    return chunks


def structure_aware_chunk(parsed: ParsedDocument) -> list[RawChunk]:
    text = parsed.full_text
    lines = text.split("\n")

    sections: list[tuple[str, int]] = []
    offset = 0
    for line in lines:
        heading = _looks_like_heading(line)
        if heading:
            sections.append((heading, offset))
        offset += len(line) + 1

    if not sections:
        return recursive_fixed_chunk(parsed)

    chunks: list[RawChunk] = []
    idx = 0

    if sections[0][1] > 0:
        preamble = text[: sections[0][1]].strip()
        if preamble:
            chunks.append(
                RawChunk(
                    text=preamble, chunk_index=idx, page_number=_page_for_offset(parsed.pages, 0),
                    section_heading="Preamble", chunking_strategy=ChunkingStrategy.STRUCTURE_AWARE.value,
                )
            )
            idx += 1

    for i, (heading, start) in enumerate(sections):
        end = sections[i + 1][1] if i + 1 < len(sections) else len(text)
        section_text = text[start:end].strip()
        if not section_text:
            continue

        if len(section_text) <= settings.chunk_size * 1.5:
            chunks.append(
                RawChunk(
                    text=section_text, chunk_index=idx, page_number=_page_for_offset(parsed.pages, start),
                    section_heading=heading, chunking_strategy=ChunkingStrategy.STRUCTURE_AWARE.value,
                )
            )
            idx += 1
        else:
            for sub_start, sub_end in _sliding_window(section_text, settings.chunk_size, settings.chunk_overlap):
                piece = section_text[sub_start:sub_end].strip()
                if not piece:
                    continue
                chunks.append(
                    RawChunk(
                        text=piece, chunk_index=idx, page_number=_page_for_offset(parsed.pages, start + sub_start),
                        section_heading=heading, chunking_strategy=ChunkingStrategy.STRUCTURE_AWARE.value,
                    )
                )
                idx += 1

    return chunks


def chunk_document(parsed: ParsedDocument, strategy: ChunkingStrategy) -> list[RawChunk]:
    if strategy == ChunkingStrategy.STRUCTURE_AWARE:
        return structure_aware_chunk(parsed)
    return recursive_fixed_chunk(parsed)
