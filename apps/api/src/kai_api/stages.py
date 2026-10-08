"""Pass-through stages for the chat route.

These satisfy the orchestrator protocols. They do not classify, search,
retrieve documents, run tools, or invent an agent reply. The response text
is the model router's candidate.
"""

from uuid import UUID

from kai_engine.context import ExecutionContext
from kai_engine.contracts import (
    ContextBundle,
    EngineRequest,
    EngineResponse,
    IntentResult,
    PlanStep,
    PlanStepKind,
    Principal,
    TaskPlan,
    ToolExecutionResult,
    VerificationResult,
)
from kai_engine.errors import UnavailableDependencyError


class PassthroughIntake:
    def accept(self, request: EngineRequest, *, context: ExecutionContext) -> EngineRequest:
        del context
        return request


class PassthroughIntent:
    async def detect(self, request: EngineRequest, *, context: ExecutionContext) -> IntentResult:
        del request, context
        return IntentResult(label="unspecified", confidence=0)


class PassthroughContext:
    async def build(
        self,
        request: EngineRequest,
        intent: IntentResult,
        *,
        context: ExecutionContext,
    ) -> ContextBundle:
        del intent, context
        return ContextBundle(organization_id=request.principal.organization_id)


class PassthroughPlanner:
    async def plan(
        self,
        request: EngineRequest,
        bundle: ContextBundle,
        *,
        context: ExecutionContext,
    ) -> TaskPlan:
        del request, bundle, context
        return TaskPlan(
            steps=[
                PlanStep(
                    id="model",
                    kind=PlanStepKind.MODEL,
                    description="Send the message to the selected model.",
                )
            ],
            required_capabilities=["text"],
        )


class ClosedToolRouter:
    """Select nothing. Execution stays closed because no tool is implemented."""

    async def select(self, plan: TaskPlan, *, context: ExecutionContext) -> list[str]:
        del plan, context
        return []

    async def execute(
        self,
        principal: Principal,
        tool_name: str,
        arguments: dict[str, object],
        *,
        context: ExecutionContext,
    ) -> ToolExecutionResult:
        del principal, tool_name, arguments, context
        raise UnavailableDependencyError


class PassthroughAgent:
    async def run(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: ExecutionContext,
    ) -> str:
        del request, plan, context
        return ""


class PassthroughMemory:
    async def retrieve(self, request: EngineRequest, *, context: ExecutionContext) -> list[UUID]:
        del request, context
        return []


class AcceptingVerifier:
    """No verification policy is defined. The candidate is accepted as text."""

    async def verify(
        self,
        request: EngineRequest,
        candidate: str,
        *,
        context: ExecutionContext,
    ) -> VerificationResult:
        del request, candidate, context
        return VerificationResult(accepted=True, reasons=[])


class ModelTextResponder:
    async def compose(
        self,
        request: EngineRequest,
        candidate: str,
        verification: VerificationResult,
        *,
        context: ExecutionContext,
    ) -> EngineResponse:
        selected = context.selected_model
        return EngineResponse(
            request_id=request.request_id,
            organization_id=request.principal.organization_id,
            message=candidate,
            model_id=None if selected is None else selected.model_id,
            provider_id=None if selected is None else selected.provider_id,
            verified=verification.accepted,
        )
