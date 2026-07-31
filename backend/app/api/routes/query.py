"""
Full RAG query endpoint. Thin wrapper around
services/rag_pipeline.execute_rag_query — see that module for the actual
pipeline. Kept as its own stateless endpoint (not chat-backed) for
one-off queries and for backward compatibility with anything already
calling it directly (e.g. the evaluation runner's design intentionally
uses services/pipeline.py instead, not this route, but external API
consumers may still depend on this exact endpoint).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.models.schemas import QueryRequest, QueryResponse
from app.services.rag_pipeline import execute_rag_query

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def run_query(request: QueryRequest, db: Session = Depends(get_db)):
    return execute_rag_query(
        request.question, db, top_k=request.top_k, include_retrieval_debug=request.include_retrieval_debug
    )
