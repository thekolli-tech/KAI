"""Health report. Dependency URLs are never included."""

from pydantic import BaseModel, ConfigDict

from kai_api.composition import build_provider_registry, model_runtime_state
from kai_api.config import Settings
from kai_api.product import ProductConfig
from kai_api.status import CheckState


class HealthChecks(BaseModel):
    model_config = ConfigDict(frozen=True)

    api: CheckState
    engine: CheckState
    model_runtime: CheckState
    postgres: CheckState
    redis: CheckState
    qdrant: CheckState
    minio: CheckState


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    service: str
    version: str
    phase: int
    environment: str
    checks: HealthChecks


def _dependency_state(value: str) -> CheckState:
    if value.strip() == "":
        return CheckState.NOT_CONFIGURED
    return CheckState.CONFIGURED_UNCHECKED


def build_health(settings: Settings, product: ProductConfig) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="kai-api",
        version=product.version,
        phase=product.phase,
        environment=settings.kai_env.value,
        checks=HealthChecks(
            api=CheckState.OK,
            engine=CheckState.INTERFACE_ONLY,
            model_runtime=model_runtime_state(build_provider_registry()),
            postgres=_dependency_state(settings.database_url),
            redis=_dependency_state(settings.redis_url),
            qdrant=_dependency_state(settings.qdrant_url),
            minio=_dependency_state(settings.minio_endpoint),
        ),
    )
