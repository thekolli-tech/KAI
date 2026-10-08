"""FastAPI application factory."""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kai_api.config import get_settings
from kai_api.health import HealthResponse, build_health
from kai_api.middleware import RequestIdMiddleware
from kai_api.product import get_product_config

api_router = APIRouter()
probe_router = APIRouter()


@api_router.get("/health", response_model=HealthResponse)
async def api_health() -> HealthResponse:
    return build_health(get_settings(), get_product_config())


@probe_router.get("/health", response_model=HealthResponse)
async def probe_health() -> HealthResponse:
    return build_health(get_settings(), get_product_config())


def create_app() -> FastAPI:
    settings = get_settings()
    product = get_product_config()
    logging.basicConfig(level=settings.kai_log_level)
    app = FastAPI(
        title=f"{product.product} API",
        version=product.version,
        summary=f"{product.product} by {product.maker}",
        description=(
            "Phase 1 serves health checks. Chat, models, tools, and agents "
            "are interfaces only and are not exposed yet."
        ),
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.kai_web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(probe_router)
    return app
