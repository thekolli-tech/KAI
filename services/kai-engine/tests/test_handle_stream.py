"""Cancellation between streamed chunks stops the provider stream."""

import asyncio
from uuid import uuid4

from kai_engine.context import CancellationToken
from kai_engine.contracts import (
    ContextBundle,
    EngineRequest,
    EngineResponse,
    IntentResult,
    ModelChoice,
    PlanStep,
    PlanStepKind,
    Principal,
    TaskPlan,
    VerificationResult,
)
from kai_engine.errors import EngineErrorKind, UnavailableDependencyError
from kai_engine.events import RunEventType
from kai_engine.orchestrator import KaiEngineOrchestrator


class _Idle:
    def accept(self, request: EngineRequest, *, context: object) -> EngineRequest:
        del context
        return request

    async def detect(self, request: EngineRequest, *, context: object) -> IntentResult:
        del request, context
        return IntentResult(label="unspecified", confidence=0)

    async def build(
        self,
        request: EngineRequest,
        intent: IntentResult,
        *,
        context: object,
    ) -> ContextBundle:
        del intent, context
        return ContextBundle(organization_id=request.principal.organization_id)

    async def plan(
        self,
        request: EngineRequest,
        bundle: ContextBundle,
        *,
        context: object,
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

    async def select(self, plan: TaskPlan, *, context: object) -> list[str]:
        del plan, context
        return []

    async def execute(
        self,
        principal: Principal,
        tool_name: str,
        arguments: dict[str, object],
        *,
        context: object,
    ) -> object:
        del principal, tool_name, arguments, context
        raise UnavailableDependencyError

    async def run(self, request: EngineRequest, plan: TaskPlan, *, context: object) -> str:
        del request, plan, context
        return ""

    async def retrieve(self, request: EngineRequest, *, context: object) -> list[object]:
        del request, context
        return []

    async def verify(
        self,
        request: EngineRequest,
        candidate: str,
        *,
        context: object,
    ) -> VerificationResult:
        del request, candidate, context
        return VerificationResult(accepted=True, reasons=[])

    async def compose(
        self,
        request: EngineRequest,
        candidate: str,
        verification: VerificationResult,
        *,
        context: object,
    ) -> EngineResponse:
        del context
        return EngineResponse(
            request_id=request.request_id,
            organization_id=request.principal.organization_id,
            message=candidate,
            model_id="mock-text",
            provider_id="mock",
            verified=verification.accepted,
        )


class _Router:
    def __init__(self, token: CancellationToken) -> None:
        self._token = token
        self.closed = False
        self.produced: list[str] = []

    async def select(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: object,
    ) -> ModelChoice:
        del request, plan, context
        return ModelChoice(provider_id="mock", model_id="mock-text")

    async def execute(self, request: EngineRequest, selection: ModelChoice) -> str:
        del request, selection
        raise AssertionError("the stream path calls stream")

    async def stream(self, request: EngineRequest, selection: ModelChoice):
        del request, selection
        try:
            self.produced.append("alpha")
            yield "alpha"
            self._token.cancel()
            self.produced.append("beta")
            yield "beta"
            self.produced.append("gamma")
            yield "gamma"
        finally:
            self.closed = True


def test_cancellation_between_chunks_stops_the_stream() -> None:
    token = CancellationToken()
    router = _Router(token)
    idle = _Idle()
    engine = KaiEngineOrchestrator(
        intake=idle,
        intent=idle,
        context=idle,
        planner=idle,
        model_router=router,
        tool_router=idle,
        agent=idle,
        memory=idle,
        verifier=idle,
        responder=idle,
    )
    request = EngineRequest(
        request_id=uuid4(),
        principal=Principal(user_id=uuid4(), organization_id=uuid4()),
        message="stream",
    )

    async def collect() -> list[object]:
        return [event async for event in engine.handle_stream(request, cancellation=token)]

    events = asyncio.run(collect())
    deltas = [event.delta for event in events if event.type is RunEventType.DELTA]
    assert deltas == ["alpha"]
    assert events[-1].type is RunEventType.FAILED
    assert events[-1].error is not None
    assert events[-1].error["kind"] == EngineErrorKind.CANCELLED.value
    assert "gamma" not in router.produced
    assert router.closed
    assert RunEventType.COMPLETED not in [event.type for event in events]
    assert "Traceback" not in events[-1].error["message"]
