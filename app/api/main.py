"""FastAPI application factory and middleware."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import events, health, kpis
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("app_starting", env=settings.app_env, version=__version__)
    yield
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Realtime product analytics pipeline with Kafka, PostgreSQL, and Redis",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, tags=["Health"])
    app.include_router(events.router, tags=["Events"])
    app.include_router(kpis.router, tags=["KPIs"])

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        status = 400 if exc.__class__.__name__ == "ValidationError" else 500
        logger.error("app_error", error=exc.message, details=exc.details, path=request.url.path)
        return JSONResponse(
            status_code=status,
            content={"error": exc.message, "details": exc.details},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.error("unhandled_error", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "details": None},
        )

    return app


app = create_app()
