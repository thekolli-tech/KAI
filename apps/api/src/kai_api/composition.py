"""Composition root for the local model runtime.

The engine never constructs a provider. This module does.
"""

from kai_api.model_router import RegisteredModelRouter
from kai_api.status import CheckState
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


def build_model_router() -> RegisteredModelRouter:
    return RegisteredModelRouter(
        registry=build_provider_registry(),
        provider_id=MOCK_PROVIDER_ID,
        model_id=MOCK_MODEL_ID,
    )


def model_runtime_state(registry: ProviderRegistry) -> CheckState:
    """Report the local mock without describing it as production inference."""

    provider_ids = registry.provider_ids()
    if provider_ids == (MOCK_PROVIDER_ID,):
        return CheckState.MOCK
    return CheckState.INTERFACE_ONLY
