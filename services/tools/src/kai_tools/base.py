"""Tool boundary.

Tools declare permissions and receive an organization-scoped context.
A tool implementation must not spawn a shell. Future code execution
belongs in a sandbox, not in this interface.
"""

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToolContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    user_id: UUID
    granted_permissions: tuple[str, ...]


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: str
    succeeded: bool
    output: str
    error: str | None = None


class ToolSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=64)
    description: str
    input_schema: dict[str, object]
    permissions: tuple[str, ...]
    implemented: bool


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict[str, object]
    permissions: tuple[str, ...]

    async def execute(self, arguments: dict[str, object], context: ToolContext) -> ToolResult:
        """Run the tool for one organization. Refuse missing permissions."""
