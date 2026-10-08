"""Provider registry tests."""

import pytest

from kai_model_runtime import (
    MockModelProvider,
    ModelCapabilities,
    ModelCapability,
    ProviderRegistry,
)
from kai_model_runtime.errors import (
    RegistryConfigurationError,
    UnknownModelError,
    UnknownProviderError,
)


class _Provider:
    def __init__(self, provider_id: str, model_id: str) -> None:
        self.provider_id = provider_id
        self.model_id = model_id

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            provider_id=self.provider_id,
            model_id=self.model_id,
            capabilities=(ModelCapability.TEXT,),
            max_context_tokens=8,
        )


def test_resolve_returns_the_injected_provider() -> None:
    provider = _Provider("mock", "mock-text")
    registry = ProviderRegistry({"mock": provider})
    assert registry.resolve("mock", "mock-text") is provider
    assert registry.provider_ids() == ("mock",)


def test_unknown_provider_and_model_are_typed() -> None:
    registry = ProviderRegistry({"mock": _Provider("mock", "mock-text")})
    with pytest.raises(UnknownProviderError) as missing_provider:
        registry.resolve("other", "mock-text")
    assert missing_provider.value.code == "unknown_provider"
    with pytest.raises(UnknownModelError) as missing_model:
        registry.resolve("mock", "other")
    assert missing_model.value.model_id == "other"


def test_provider_id_must_match_the_registry_key() -> None:
    with pytest.raises(RegistryConfigurationError):
        ProviderRegistry({"mock": _Provider("other", "mock-text")})


def test_registries_do_not_share_state() -> None:
    first = ProviderRegistry({"mock": _Provider("mock", "mock-text")})
    second = ProviderRegistry({})
    assert first.provider_ids() == ("mock",)
    assert second.provider_ids() == ()


def test_mock_provider_can_be_registered() -> None:
    provider = MockModelProvider(provider_id="mock", model_id="mock-text")
    resolved = ProviderRegistry({provider.provider_id: provider}).resolve("mock", "mock-text")
    assert resolved is provider
