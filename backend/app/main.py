from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.exceptions import register_exception_handlers
from app.models.database import SessionLocal, init_db
from app.retrieval.sparse import bm25_store

from app.api.routes import health, documents, query, retrieval, evaluation, chats

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    db = SessionLocal()
    try:
        bm25_store.refresh(db)
    finally:
        db.close()

    logger.info(
        "biorag_startup",
        extra={"event_data": {"app_env": settings.app_env, "embedding_model": settings.embedding_model,
                               "reranker_model": settings.reranker_model, "llm_model": settings.llm_model}},
    )
    yield


app = FastAPI(
    title=settings.app_name, description="Biomedical AI-Powered Research Intelligence System", version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(documents.router, prefix=settings.api_v1_prefix)
app.include_router(query.router, prefix=settings.api_v1_prefix)
app.include_router(retrieval.router, prefix=settings.api_v1_prefix)
app.include_router(evaluation.router, prefix=settings.api_v1_prefix)
app.include_router(chats.router, prefix=settings.api_v1_prefix)
