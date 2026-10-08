"""Provider boundary for KAI.

Concrete providers implement ModelProvider. The engine never imports them.
MockModelProvider is a local deterministic stand-in for tests and development.
It is not a production intelligence provider.
"""

from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class ModelCapability(StrEnum):
    TEXT = "text"
    STREAM = "stream"
    TOOLS = "tools"
    VISION = "vision"


class ModelCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_id: str
    model_id: str
    capabilities: tuple[ModelCapability, ...]
    max_context_tokens: int = Field(gt=0)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: str
    prompt: str = Field(min_length=1)
    system: str | None = None


class ModelOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_id: str
    model_id: str
    text: str
    finish_reason: str


class ModelProvider(Protocol):
    provider_id: str

    async def generate(self, request: GenerateRequest) -> ModelOutput:
        """Return one normalized completion."""

    def stream(self, request: GenerateRequest) -> AsyncIterator[str]:
        """Yield normalized text chunks."""

    def get_capabilities(self) -> ModelCapabilities:
        """Describe what this provider can do."""

    async def health_check(self) -> bool:
        """Report whether this provider process is reachable."""
