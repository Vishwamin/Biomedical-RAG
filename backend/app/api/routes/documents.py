from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import settings
from app.core.exceptions import DocumentNotFoundError
from app.ingestion.service import ingest_document
from app.models.database import ChunkRecord, DocumentRecord
from app.models.schemas import ChunkingStrategy, ChunkMetadata, DocumentMetadata
from app.retrieval import dense
from app.retrieval.sparse import bm25_store

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentMetadata, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    chunking_strategy: ChunkingStrategy | None = Query(default=None),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read()
    return ingest_document(file_bytes, file.filename, db, strategy=chunking_strategy)


@router.get("", response_model=list[DocumentMetadata])
async def list_documents(db: Session = Depends(get_db)):
    records = db.query(DocumentRecord).order_by(DocumentRecord.uploaded_at.desc()).all()
    return [DocumentMetadata.model_validate(r, from_attributes=True) for r in records]


@router.get("/{document_id}", response_model=DocumentMetadata)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    record = db.query(DocumentRecord).filter_by(document_id=document_id).first()
    if not record:
        raise DocumentNotFoundError(f"Document '{document_id}' not found.", details={"document_id": document_id})
    return DocumentMetadata.model_validate(record, from_attributes=True)


@router.get("/{document_id}/chunks", response_model=list[ChunkMetadata])
async def list_document_chunks(document_id: str, db: Session = Depends(get_db)):
    doc_record = db.query(DocumentRecord).filter_by(document_id=document_id).first()
    if not doc_record:
        raise DocumentNotFoundError(f"Document '{document_id}' not found.", details={"document_id": document_id})
    chunk_records = (
        db.query(ChunkRecord).filter_by(document_id=document_id).order_by(ChunkRecord.chunk_index).all()
    )
    return [ChunkMetadata.model_validate(c, from_attributes=True) for c in chunk_records]


@router.delete("/{document_id}")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    record = db.query(DocumentRecord).filter_by(document_id=document_id).first()
    if not record:
        raise DocumentNotFoundError(f"Document '{document_id}' not found.", details={"document_id": document_id})

    db.query(ChunkRecord).filter_by(document_id=document_id).delete()
    db.delete(record)
    db.commit()

    dense.delete_document(document_id)
    bm25_store.refresh(db)

    for stored_file in Path(settings.documents_directory).glob(f"{document_id}.*"):
        stored_file.unlink(missing_ok=True)

    return {"status": "deleted", "document_id": document_id}
