"""
Ingestion orchestration: parse, chunk, embed, index. Status only becomes
INDEXED once the document actually has vectors in ChromaDB and is in the
BM25 index.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DuplicateDocumentError, IngestionError, UnsupportedFileTypeError
from app.core.logging import get_logger
from app.ingestion.chunker import chunk_document
from app.ingestion.metadata import compute_content_hash, generate_chunk_id, generate_document_id
from app.ingestion.parser import SUPPORTED_EXTENSIONS, parse_document
from app.models.database import ChunkRecord, DocumentRecord
from app.models.schemas import ChunkingStrategy, DocumentMetadata, DocumentStatus
from app.retrieval import dense
from app.retrieval.sparse import bm25_store

logger = get_logger(__name__)


def _approximate_token_count(text: str) -> int:
    return len(text.split())


def ingest_document(
    file_bytes: bytes, original_filename: str, db: Session, strategy: ChunkingStrategy | None = None,
) -> DocumentMetadata:
    suffix = Path(original_filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
            details={"filename": original_filename},
        )

    content_hash = compute_content_hash(file_bytes)
    existing = db.query(DocumentRecord).filter_by(content_hash=content_hash).first()
    if existing:
        raise DuplicateDocumentError(
            f"Document with identical content already ingested as '{existing.document_id}'.",
            details={"existing_document_id": existing.document_id, "existing_filename": existing.source_filename},
        )

    document_id = generate_document_id()
    documents_dir = Path(settings.documents_directory)
    documents_dir.mkdir(parents=True, exist_ok=True)
    stored_path = documents_dir / f"{document_id}{suffix}"
    stored_path.write_bytes(file_bytes)

    record = DocumentRecord(
        document_id=document_id, source_filename=original_filename, document_title=None,
        content_hash=content_hash, status=DocumentStatus.PENDING.value, page_count=None, chunk_count=0,
    )
    db.add(record)
    db.commit()

    try:
        record.status = DocumentStatus.PROCESSING.value
        db.commit()

        parsed = parse_document(stored_path)
        chosen_strategy = strategy or ChunkingStrategy(settings.default_chunking_strategy)
        raw_chunks = chunk_document(parsed, chosen_strategy)

        if not raw_chunks:
            raise IngestionError("Parsing succeeded but produced zero chunks.", details={"document_id": document_id})

        chunk_records: list[ChunkRecord] = []
        for raw in raw_chunks:
            chunk_record = ChunkRecord(
                chunk_id=generate_chunk_id(document_id, raw.chunk_index), document_id=document_id,
                source_filename=original_filename, document_title=parsed.detected_title,
                page_number=raw.page_number, section_heading=raw.section_heading, chunk_index=raw.chunk_index,
                text=raw.text, character_count=len(raw.text), token_count=_approximate_token_count(raw.text),
                chunking_strategy=raw.chunking_strategy,
            )
            db.add(chunk_record)
            chunk_records.append(chunk_record)

        record.document_title = parsed.detected_title
        record.page_count = parsed.page_count
        record.chunk_count = len(raw_chunks)
        db.commit()

        dense.add_chunks(chunk_records)
        bm25_store.refresh(db)

        record.status = DocumentStatus.INDEXED.value
        db.commit()

        logger.info(
            "document_ingested",
            extra={"event_data": {"document_id": document_id, "chunk_count": len(raw_chunks),
                                   "strategy": chosen_strategy.value, "page_count": parsed.page_count}},
        )

    except Exception as exc:
        record.status = DocumentStatus.FAILED.value
        db.commit()
        logger.error("document_ingestion_failed", extra={"event_data": {"document_id": document_id, "error": str(exc)}})
        if isinstance(exc, IngestionError):
            raise
        raise IngestionError(f"Failed to ingest document: {exc}", details={"document_id": document_id}) from exc

    db.refresh(record)
    return DocumentMetadata.model_validate(record, from_attributes=True)
