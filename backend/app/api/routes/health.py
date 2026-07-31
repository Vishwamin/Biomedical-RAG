from fastapi import APIRouter

from app.core.config import settings
from app.models.database import database_is_reachable
from app.models.schemas import HealthResponse, HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    db_ok = database_is_reachable()
    return HealthResponse(
        status=HealthStatus.OK if db_ok else HealthStatus.DEGRADED,
        app_name=settings.app_name, app_env=settings.app_env,
        embedding_model=settings.embedding_model, reranker_model=settings.reranker_model,
        llm_provider=settings.llm_provider, llm_model=settings.llm_model,
        database_reachable=db_ok,
    )
