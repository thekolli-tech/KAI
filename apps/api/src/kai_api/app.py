"""FastAPI application factory."""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kai_api.access import BoundaryAuthorizer, LocalDevelopmentAuthenticator
from kai_api.chat import install_chat, install_error_handlers
from kai_api.composition import build_engine, build_model_router
from kai_api.config import get_settings
from kai_api.health import HealthResponse, build_health
from kai_api.middleware import RequestIdMiddleware
from kai_api.product import get_product_config
from kai_engine.interfaces import VerificationEngine
from kai_model_runtime import ModelProvider

api_router = APIRouter()
probe_router = APIRouter()
install_chat(api_router)


@api_router.get("/health", response_model=HealthResponse)
async def api_health() -> HealthResponse:
    return build_health(get_settings(), get_product_config())


@probe_router.get("/health", response_model=HealthResponse)
async def probe_health() -> HealthResponse:
    return build_health(get_settings(), get_product_config())


def create_app(
    *,
    model_provider: ModelProvider | None = None,
    verifier: VerificationEngine | None = None,
) -> FastAPI:
    settings = get_settings()
    product = get_product_config()
    logging.basicConfig(level=settings.kai_log_level)
    app = FastAPI(
        title=f"{product.product} API",
        version=product.version,
        summary=f"{product.product} by {product.maker}",
        description=(
            "Health checks and POST /api/v1/chat are exposed. Chat uses the local "
            "mock model. It is not a hosted provider."
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
    router = build_model_router(model_provider)
    app.state.model_router = router
    app.state.engine = build_engine(router, verifier=verifier)
    app.state.authenticator = LocalDevelopmentAuthenticator(settings)
    app.state.authorizer = BoundaryAuthorizer()
    install_error_handlers(app)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(probe_router)
    return app
