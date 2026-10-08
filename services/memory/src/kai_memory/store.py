"""Memory storage boundary.

Structured records belong in PostgreSQL. Semantic search belongs in Qdrant.
Every method takes an organization id so a later implementation cannot query
across tenants by memory id alone. Deletion must remove both the record and
its vector.
"""

from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemoryScope(StrEnum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    PROJECT = "project"


class MemoryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    user_id: UUID
    project_id: UUID | None = None
    scope: MemoryScope
    content: str = Field(min_length=1, max_length=16_000)


class MemoryQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    user_id: UUID
    scope: MemoryScope | None = None
    project_id: UUID | None = None
    text: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=8, ge=1, le=50)


class MemoryStore(Protocol):
    async def save(self, record: MemoryRecord) -> MemoryRecord:
        """Persist one memory the caller is allowed to write."""

    async def search(self, query: MemoryQuery) -> list[MemoryRecord]:
        """Search inside one organization. Exclude deleted memories."""

    async def update(self, record: MemoryRecord) -> MemoryRecord:
        """Replace content the caller is allowed to change."""

    async def delete(self, *, organization_id: UUID, memory_id: UUID) -> None:
        """Honor a deletion request for one organization."""
