"""Search boundary for a future self-hosted search layer.

web_search and web_fetch will call this port. Phase 1 does not fetch the web.
"""

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    async def search(self, request: SearchRequest) -> list[SearchHit]:
        """Return hits from the configured search layer."""
