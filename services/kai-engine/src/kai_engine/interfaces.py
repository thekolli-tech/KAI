"""Stage interfaces for the KAI Engine.

Stages stay free of a concrete model provider. ``KaiEngineOrchestrator``
calls these protocols in order and passes the shared ``ExecutionContext``.
``ModelRouter.execute`` and ``ModelRouter.stream`` are the invocation ports.
The concrete router lives outside this package and is the only caller of
``ModelProvider``.
"""

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from kai_engine.context import CancellationToken, ExecutionContext
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
from kai_engine.events import RunEvent


class RequestIntake(Protocol):
    def accept(self, request: EngineRequest, *, context: ExecutionContext) -> EngineRequest:
        """Validate an already typed request before any stage runs."""


class IntentEngine(Protocol):
    async def detect(self, request: EngineRequest, *, context: ExecutionContext) -> IntentResult:
        """Classify what the user is asking for."""


class ContextEngine(Protocol):
    async def build(
        self,
        request: EngineRequest,
        intent: IntentResult,
        *,
        context: ExecutionContext,
    ) -> ContextBundle:
        """Assemble the organization-scoped context for this request."""


class PlanningEngine(Protocol):
    async def plan(
        self,
        request: EngineRequest,
        bundle: ContextBundle,
        *,
        context: ExecutionContext,
    ) -> TaskPlan:
        """Turn the request into an ordered set of model, tool, and agent steps."""


class ModelRouter(Protocol):
    async def select(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: ExecutionContext,
    ) -> ModelChoice:
        """Choose a provider and model. Provider SDKs stay outside the engine."""

    async def execute(self, request: EngineRequest, selection: ModelChoice) -> str:
        """Run the selected model through a provider and return normalized text."""

    def stream(
        self,
        request: EngineRequest,
        selection: ModelChoice,
    ) -> AsyncIterator[str]:
        """Yield normalized text chunks from the selected provider."""


class ToolRouter(Protocol):
    async def select(self, plan: TaskPlan, *, context: ExecutionContext) -> list[str]:
        """Choose tool names required by the plan. Does not run them."""

    async def execute(
        self,
        principal: Principal,
        tool_name: str,
        arguments: dict[str, object],
        *,
        context: ExecutionContext,
    ) -> ToolExecutionResult:
        """Run one permitted tool. Shell execution is not a tool."""


class AgentEngine(Protocol):
    async def run(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: ExecutionContext,
    ) -> str:
        """Delegate once to an agent. This is not an autonomous loop."""


class MemoryEngine(Protocol):
    async def retrieve(self, request: EngineRequest, *, context: ExecutionContext) -> list[UUID]:
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
    async def verify(
        self,
        request: EngineRequest,
        candidate: str,
        *,
        context: ExecutionContext,
    ) -> VerificationResult:
        """Check a candidate answer before it is returned."""


class ResponseEngine(Protocol):
    async def compose(
        self,
        request: EngineRequest,
        candidate: str,
        verification: VerificationResult,
        *,
        context: ExecutionContext,
    ) -> EngineResponse:
        """Shape the final response. This does not call a provider."""


class KaiEngine(Protocol):
    async def handle(self, request: EngineRequest) -> EngineResponse:
        """Run intake through response for one request."""

    def handle_stream(
        self,
        request: EngineRequest,
        *,
        cancellation: CancellationToken | None = None,
        run_id: UUID | None = None,
    ) -> AsyncIterator[RunEvent]:
        """Run the same stages, yielding public events while the model streams."""
