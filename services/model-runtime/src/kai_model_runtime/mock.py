"""Deterministic local model provider for development and tests.

This is not a production intelligence provider. It does not call a network
service and it does not require an API key.
"""

from collections.abc import AsyncIterator, Mapping

from kai_model_runtime.errors import UnknownModelError
from kai_model_runtime.provider import (
    GenerateRequest,
    ModelCapabilities,
    ModelCapability,
    ModelOutput,
)

DEFAULT_CHUNK_SIZE = 16
DEFAULT_MAX_CONTEXT_TOKENS = 4096


class MockModelProvider:
    """Return configured text, or a deterministic rendering of the prompt."""

    def __init__(
        self,
        *,
        provider_id: str,
        model_id: str,
        responses: Mapping[str, str] | None = None,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        healthy: bool = True,
    ) -> None:
        if provider_id.strip() == "" or model_id.strip() == "":
            raise ValueError("provider_id and model_id are required")
        if max_context_tokens < 1:
            raise ValueError("max_context_tokens must be positive")
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        self.provider_id = provider_id
        self._model_id = model_id
        self._responses = dict(responses or {})
        self._max_context_tokens = max_context_tokens
        self._chunk_size = chunk_size
        self._healthy = healthy

    async def generate(self, request: GenerateRequest) -> ModelOutput:
        return ModelOutput(
            provider_id=self.provider_id,
            model_id=self._model_id,
            text=self._text(request),
            finish_reason="stop",
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[str]:
        text = self._text(request)
        size = self._chunk_size
        for start in range(0, len(text), size):
            yield text[start : start + size]

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            provider_id=self.provider_id,
            model_id=self._model_id,
            capabilities=(ModelCapability.TEXT, ModelCapability.STREAM),
            max_context_tokens=self._max_context_tokens,
        )

    async def health_check(self) -> bool:
        return self._healthy

    def _text(self, request: GenerateRequest) -> str:
        if request.model_id != self._model_id:
            raise UnknownModelError(self.provider_id, request.model_id)
        configured = self._responses.get(request.prompt)
        if configured is not None:
            return configured
        if request.system is None:
            return f"{self.provider_id}:{self._model_id}:{request.prompt}"
        return f"{self.provider_id}:{self._model_id}:{request.system}:{request.prompt}"
