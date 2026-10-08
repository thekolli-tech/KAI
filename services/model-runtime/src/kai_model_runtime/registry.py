"""Explicit provider registry. Instances are injected. There is no process singleton."""

from collections.abc import Mapping

from kai_model_runtime.errors import (
    RegistryConfigurationError,
    UnknownModelError,
    UnknownProviderError,
)
from kai_model_runtime.provider import ModelProvider


class ProviderRegistry:
    """Resolve a provider id and model id to an injected ``ModelProvider``."""

    def __init__(self, providers: Mapping[str, ModelProvider]) -> None:
        stored: dict[str, ModelProvider] = {}
        for provider_id, provider in providers.items():
            if provider_id.strip() == "" or provider.provider_id != provider_id:
                raise RegistryConfigurationError()
            stored[provider_id] = provider
        self._providers = stored

    def provider_ids(self) -> tuple[str, ...]:
        return tuple(self._providers)

    def resolve(self, provider_id: str, model_id: str) -> ModelProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise UnknownProviderError(provider_id)
        capabilities = provider.get_capabilities()
        if capabilities.provider_id != provider_id or capabilities.model_id != model_id:
            raise UnknownModelError(provider_id, model_id)
        return provider
