"""Stage interfaces for the KAI Engine.

Phase 1 defines the boundaries. A later phase wires these stages into a
pipeline. There is no default implementation that pretends to reason.
"""

from typing import Protocol
from uuid import UUID

from kai_engine.contracts import (
    AuthorizationDecision,
    ContextBundle,
    EngineRequest,
    EngineResponse,
    IntentResult,
    ModelChoice,
    Principal,
    TaskPlan,
    ToolExecutionResult,
    VerificationResult,
)


class RequestIntake(Protocol):
    def accept(self, request: EngineRequest) -> EngineRequest:
        """Validate an already typed request before any stage runs."""


class IntentEngine(Protocol):
    async def detect(self, request: EngineRequest) -> IntentResult:
        """Classify what the user is asking for."""


class ContextEngine(Protocol):
    async def build(self, request: EngineRequest, intent: IntentResult) -> ContextBundle:
        """Assemble the organization-scoped context for this request."""


class PlanningEngine(Protocol):
    async def plan(self, request: EngineRequest, context: ContextBundle) -> TaskPlan:
        """Turn the request into an ordered set of model, tool, and agent steps."""


class ModelRouter(Protocol):
    async def select(self, request: EngineRequest, plan: TaskPlan) -> ModelChoice:
        """Choose a provider and model. Provider SDKs stay outside the engine."""

    async def execute(self, request: EngineRequest, selection: ModelChoice) -> str:
        """Run the selected model and return normalized text."""


class ToolRouter(Protocol):
    async def select(self, plan: TaskPlan) -> list[str]:
        """Choose tool names required by the plan. Does not run them."""

    async def execute(
        self,
        principal: Principal,
        tool_name: str,
        arguments: dict[str, object],
    ) -> ToolExecutionResult:
        """Run one permitted tool. Shell execution is not a tool."""


class AgentEngine(Protocol):
    async def run(self, request: EngineRequest, plan: TaskPlan) -> str:
        """Delegate a planned step to a named agent."""


class MemoryEngine(Protocol):
    async def retrieve(self, request: EngineRequest) -> list[UUID]:
        """Return memory ids visible to this principal's organization."""


class SecurityEngine(Protocol):
    async def authorize(
        self,
        principal: Principal,
        *,
        action: str,
        organization_id: UUID,
    ) -> AuthorizationDecision:
        """Fail closed when the action crosses an organization boundary."""


class VerificationEngine(Protocol):
    async def verify(self, request: EngineRequest, candidate: str) -> VerificationResult:
        """Check a candidate answer before it is returned."""


class ResponseEngine(Protocol):
    async def compose(
        self,
        request: EngineRequest,
        candidate: str,
        verification: VerificationResult,
    ) -> EngineResponse:
        """Shape the final response. This does not call a provider."""


class KaiEngine(Protocol):
    async def handle(self, request: EngineRequest) -> EngineResponse:
        """Run intake through response once the stages are implemented."""
