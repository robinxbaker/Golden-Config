"""FastAPI application factory and entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.observability import setup_observability

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("startup", environment=settings.ENVIRONMENT, project=settings.PROJECT_NAME)
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs",
        lifespan=lifespan,
    )

    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, str]:
        return {"name": settings.PROJECT_NAME, "docs": "/docs"}

    setup_observability(app)
    return app


app = create_app()
