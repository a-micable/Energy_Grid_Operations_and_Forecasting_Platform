from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse

from gridmind import __version__
from gridmind.api.v1.router import api_router
from gridmind.config import get_settings
from gridmind.api.middleware import CorrelationIdMiddleware, RequestLoggingMiddleware
from gridmind.core.exceptions import GridMindError

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("gridmind_starting", version=__version__, env=settings.gridmind_env)
    yield
    logger.info("gridmind_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="GridMind",
        description="Energy Grid Operations & Forecasting Platform",
        version=__version__,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs" if settings.gridmind_env != "production" else None,
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    @app.exception_handler(GridMindError)
    async def gridmind_error_handler(request: Request, exc: GridMindError) -> ORJSONResponse:
        status_code = 400
        if exc.code == "NOT_FOUND":
            status_code = 404
        elif exc.code in ("FORECAST_DRIFT", "STATE_TRANSITION_ERROR", "DISPATCH_CONFLICT"):
            status_code = 422
        return ORJSONResponse(
            status_code=status_code,
            content={"code": exc.code, "message": exc.message, "details": exc.details},
        )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "healthy", "version": __version__}

    app.include_router(api_router)
    return app


app = create_app()
