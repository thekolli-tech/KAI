"""Data contracts for the KAI Engine.

These models are the boundary between the API and later engine stages.
Nothing in this module calls a model, tool, or database.
"""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EngineStage(StrEnum):
    INTAKE = "intake"
    INTENT = "intent"
    CONTEXT = "context"
    PLANNING = "planning"
    MODEL_SELECTION = "model_selection"
    TOOL_SELECTION = "tool_selection"
    AGENT_EXECUTION = "agent_execution"
    MEMORY_RETRIEVAL = "memory_retrieval"
    TOOL_EXECUTION = "tool_execution"
    VERIFICATION = "verification"
    RESPONSE = "response"


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID
    organization_id: UUID


class EngineRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: UUID
    principal: Principal
    conversation_id: UUID | None = None
    project_id: UUID | None = None
    message: str = Field(min_length=1, max_length=32_000)
    attachment_ids: list[UUID] = Field(default_factory=list)


class IntentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0, le=1)


class ContextBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    conversation_summary: str | None = None
    memory_ids: list[UUID] = Field(default_factory=list)
    document_ids: list[UUID] = Field(default_factory=list)


class PlanStepKind(StrEnum):
    MODEL = "model"
    TOOL = "tool"
    AGENT = "agent"
    RESPOND = "respond"


class PlanStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    kind: PlanStepKind
    description: str = Field(min_length=1, max_length=500)
    tool_name: str | None = None
    agent_name: str | None = None


class TaskPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    steps: list[PlanStep]
    required_capabilities: list[str]


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: str
    succeeded: bool
    output: str
    error: str | None = None


class VerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    accepted: bool
    reasons: list[str] = Field(default_factory=list)


class EngineResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: UUID
    organization_id: UUID
    message: str
    model_id: str | None = None
    provider_id: str | None = None
    verified: bool = False


class AuthorizationDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    reason: str


class ModelChoice(BaseModel):
    """A selected provider and model. The engine never imports a vendor SDK."""

    model_config = ConfigDict(frozen=True)

    provider_id: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=128)
