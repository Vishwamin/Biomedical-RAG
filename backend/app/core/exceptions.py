"""
Custom exceptions and their FastAPI handlers.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class BioRAGException(Exception):
    status_code = 500
    error_code = "internal_error"

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class DocumentNotFoundError(BioRAGException):
    status_code = 404
    error_code = "document_not_found"


class DuplicateDocumentError(BioRAGException):
    status_code = 409
    error_code = "duplicate_document"


class UnsupportedFileTypeError(BioRAGException):
    status_code = 400
    error_code = "unsupported_file_type"


class IngestionError(BioRAGException):
    status_code = 422
    error_code = "ingestion_failed"


class RetrievalError(BioRAGException):
    status_code = 500
    error_code = "retrieval_failed"


class GenerationError(BioRAGException):
    status_code = 502
    error_code = "generation_failed"


class EvaluationError(BioRAGException):
    status_code = 500
    error_code = "evaluation_failed"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BioRAGException)
    async def biorag_exception_handler(request: Request, exc: BioRAGException):
        logger.error(
            "handled_exception",
            extra={
                "event_data": {
                    "error_code": exc.error_code,
                    "path": str(request.url),
                    "details": exc.details,
                }
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error_code, "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled_exception", extra={"event_data": {"path": str(request.url)}})
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "An unexpected error occurred.", "details": {}},
        )
