"""Agent boundary.

An agent names the tools it may call. It does not receive a shell.
Autonomous loops are intentionally out of scope for this phase.
"""

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    user_id: UUID
    instruction: str = Field(min_length=1, max_length=32_000)
    project_id: UUID | None = None


class AgentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent_name: str
    output: str
    tool_names: tuple[str, ...] = ()


class AgentSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    capabilities: tuple[str, ...]
    tools: tuple[str, ...]
    permissions: tuple[str, ...]
    implemented: bool


class Agent(Protocol):
    name: str
    description: str
    capabilities: tuple[str, ...]
    tools: tuple[str, ...]
    permissions: tuple[str, ...]

    async def execute(self, task: AgentTask) -> AgentResult:
        """Run one task inside the caller's organization."""
