"""Composition root for the local model runtime.

The engine never constructs a provider. This module does.
"""

from kai_api.model_router import RegisteredModelRouter
from kai_api.stages import (
    AcceptingVerifier,
    ClosedToolRouter,
    ModelTextResponder,
    PassthroughAgent,
    PassthroughContext,
    PassthroughIntake,
    PassthroughIntent,
    PassthroughMemory,
    PassthroughPlanner,
)
from kai_api.status import CheckState
from kai_engine.interfaces import VerificationEngine
from kai_engine.orchestrator import KaiEngineOrchestrator
from kai_model_runtime import MockModelProvider, ModelProvider
from kai_model_runtime.registry import ProviderRegistry

MOCK_PROVIDER_ID = "mock"
MOCK_MODEL_ID = "mock-text"


def build_provider_registry() -> ProviderRegistry:
    provider: ModelProvider = MockModelProvider(
        provider_id=MOCK_PROVIDER_ID,
        model_id=MOCK_MODEL_ID,
    )
    return ProviderRegistry({provider.provider_id: provider})


def build_model_router(provider: ModelProvider | None = None) -> RegisteredModelRouter:
    if provider is None:
        registry = build_provider_registry()
    else:
        registry = ProviderRegistry({provider.provider_id: provider})
    return RegisteredModelRouter(
        registry=registry,
        provider_id=MOCK_PROVIDER_ID,
        model_id=MOCK_MODEL_ID,
    )


def build_engine(
    router: RegisteredModelRouter,
    *,
    verifier: VerificationEngine | None = None,
) -> KaiEngineOrchestrator:
    return KaiEngineOrchestrator(
        intake=PassthroughIntake(),
        intent=PassthroughIntent(),
        context=PassthroughContext(),
        planner=PassthroughPlanner(),
        model_router=router,
        tool_router=ClosedToolRouter(),
        agent=PassthroughAgent(),
        memory=PassthroughMemory(),
        verifier=verifier if verifier is not None else AcceptingVerifier(),
        responder=ModelTextResponder(),
    )


def model_runtime_state(registry: ProviderRegistry) -> CheckState:
    """Report the local mock without describing it as production inference."""

    provider_ids = registry.provider_ids()
    if provider_ids == (MOCK_PROVIDER_ID,):
        return CheckState.MOCK
    return CheckState.INTERFACE_ONLY
