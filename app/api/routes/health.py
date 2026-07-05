"""Health check endpoint."""

from fastapi import APIRouter

from app import __version__
from app.api.schemas import HealthResponse
from app.storage.postgres import get_postgres_store
from app.storage.redis_cache import get_redis_cache

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    postgres = get_postgres_store()
    redis = get_redis_cache()

    components = {
        "postgres": postgres.health_check(),
        "redis": redis.health_check(),
    }
    all_healthy = all(components.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version=__version__,
        components=components,
    )
