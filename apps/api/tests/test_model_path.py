"""Engine path through the composed router and MockModelProvider."""

import asyncio
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from kai_api.app import create_app
from kai_api.composition import (
    MOCK_MODEL_ID,
    MOCK_PROVIDER_ID,
    build_model_router,
    build_provider_registry,
    model_runtime_state,
)
from kai_api.model_router import RegisteredModelRouter
from kai_api.status import CheckState
from kai_engine.context import CancellationToken, ExecutionContext
from kai_engine.contracts import (
    ContextBundle,
    EngineRequest,
    EngineResponse,
    EngineStage,
    IntentResult,
    PlanStep,
    PlanStepKind,
    Principal,
    TaskPlan,
    ToolExecutionResult,
    VerificationResult,
)
from kai_engine.orchestrator import KaiEngineOrchestrator
from kai_model_runtime import MockModelProvider, ProviderRegistry

MESSAGE = "Inspect the pipeline"
EXPECTED = f"{MOCK_PROVIDER_ID}:{MOCK_MODEL_ID}:{MESSAGE}"


def _request() -> EngineRequest:
    return EngineRequest(
        request_id=uuid4(),
        principal=Principal(user_id=uuid4(), organization_id=uuid4()),
        conversation_id=uuid4(),
        message=MESSAGE,
    )


class _Stages:
    def __init__(self) -> None:
        self.order: list[str] = []

    def _hit(self, stage: EngineStage) -> None:
        self.order.append(stage.value)

    def accept(self, request: EngineRequest, *, context: ExecutionContext) -> EngineRequest:
        self._hit(EngineStage.INTAKE)
        assert context.model_result is None
        return request

    async def detect(self, request: EngineRequest, *, context: ExecutionContext) -> IntentResult:
        del context
        self._hit(EngineStage.INTENT)
        return IntentResult(label="unclear", confidence=0)

    async def build(
        self,
        request: EngineRequest,
        intent: IntentResult,
        *,
        context: ExecutionContext,
    ) -> ContextBundle:
        del intent, context
        self._hit(EngineStage.CONTEXT)
        return ContextBundle(organization_id=request.principal.organization_id)

    async def plan(
        self,
        request: EngineRequest,
        bundle: ContextBundle,
        *,
        context: ExecutionContext,
    ) -> TaskPlan:
        del request, bundle
        self._hit(EngineStage.PLANNING)
        assert context.model_result is None
        return TaskPlan(
            steps=[
                PlanStep(
                    id="agent-1",
                    kind=PlanStepKind.AGENT,
                    description="Delegate once",
                    agent_name="ResearchAgent",
                )
            ],
            required_capabilities=[],
        )

    async def select_tools(self, plan: TaskPlan, *, context: ExecutionContext) -> list[str]:
        del plan
        self._hit(EngineStage.TOOL_SELECTION)
        assert context.model_result == EXPECTED
        assert context.selected_model is not None
        assert context.selected_model.provider_id == MOCK_PROVIDER_ID
        return ["file_read"]

    async def execute_tool(
        self,
        principal: Principal,
        tool_name: str,
        arguments: dict[str, object],
        *,
        context: ExecutionContext,
    ) -> ToolExecutionResult:
        del principal, arguments
        self._hit(EngineStage.TOOL_EXECUTION)
        assert context.model_result == EXPECTED
        return ToolExecutionResult(tool_name=tool_name, succeeded=True, output="")

    async def run_agent(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: ExecutionContext,
    ) -> str:
        del request, plan
        self._hit(EngineStage.AGENT_EXECUTION)
        assert context.model_result == EXPECTED
        return "agent-output"

    async def retrieve(self, request: EngineRequest, *, context: ExecutionContext) -> list[UUID]:
        del request, context
        self._hit(EngineStage.MEMORY_RETRIEVAL)
        return []

    async def verify(
        self,
        request: EngineRequest,
        candidate: str,
        *,
        context: ExecutionContext,
    ) -> VerificationResult:
        del request
        self._hit(EngineStage.VERIFICATION)
        assert candidate == EXPECTED
        assert context.model_result == candidate
        assert context.agent_result == "agent-output"
        return VerificationResult(accepted=True, reasons=[])

    async def compose(
        self,
        request: EngineRequest,
        candidate: str,
        verification: VerificationResult,
        *,
        context: ExecutionContext,
    ) -> EngineResponse:
        self._hit(EngineStage.RESPONSE)
        assert candidate == EXPECTED
        assert context.selected_model is not None
        return EngineResponse(
            request_id=request.request_id,
            organization_id=request.principal.organization_id,
            message=candidate,
            model_id=context.selected_model.model_id,
            provider_id=context.selected_model.provider_id,
            verified=verification.accepted,
        )


class _Tools:
    def __init__(self, stages: _Stages) -> None:
        self._stages = stages

    async def select(self, plan: TaskPlan, *, context: ExecutionContext) -> list[str]:
        return await self._stages.select_tools(plan, context=context)

    async def execute(
        self,
        principal: Principal,
        tool_name: str,
        arguments: dict[str, object],
        *,
        context: ExecutionContext,
    ) -> ToolExecutionResult:
        return await self._stages.execute_tool(principal, tool_name, arguments, context=context)


class _Agent:
    def __init__(self, stages: _Stages) -> None:
        self._stages = stages

    async def run(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: ExecutionContext,
    ) -> str:
        return await self._stages.run_agent(request, plan, context=context)


def test_mock_provider_output_reaches_verification_and_response() -> None:
    stages = _Stages()
    provider = MockModelProvider(provider_id=MOCK_PROVIDER_ID, model_id=MOCK_MODEL_ID)
    router = RegisteredModelRouter(
        registry=ProviderRegistry({provider.provider_id: provider}),
        provider_id=MOCK_PROVIDER_ID,
        model_id=MOCK_MODEL_ID,
    )
    engine = KaiEngineOrchestrator(
        intake=stages,
        intent=stages,
        context=stages,
        planner=stages,
        model_router=router,
        tool_router=_Tools(stages),
        agent=_Agent(stages),
        memory=stages,
        verifier=stages,
        responder=stages,
    )
    request = _request()
    response = asyncio.run(engine.handle(request, cancellation=CancellationToken(), run_id=uuid4()))

    assert stages.order == [
        "intake",
        "intent",
        "context",
        "planning",
        "tool_selection",
        "agent_execution",
        "memory_retrieval",
        "tool_execution",
        "verification",
        "response",
    ]
    assert response.message == EXPECTED
    assert response.model_id == MOCK_MODEL_ID
    assert response.provider_id == MOCK_PROVIDER_ID
    assert response.verified is True
    assert response.request_id == request.request_id


def test_runtime_state_distinguishes_mock_from_an_empty_registry() -> None:
    assert model_runtime_state(ProviderRegistry({})) is CheckState.INTERFACE_ONLY
    assert model_runtime_state(build_provider_registry()) is CheckState.MOCK


def test_app_registers_the_mock_router_and_does_not_expose_chat() -> None:
    app = create_app()
    router = app.state.model_router
    assert isinstance(router, RegisteredModelRouter)
    client = TestClient(app)
    assert client.post("/api/v1/chat").status_code == 404
    composed = build_model_router()
    request = _request()

    async def run() -> str:
        choice = await composed.select(
            request,
            TaskPlan(steps=[], required_capabilities=[]),
            context=ExecutionContext(
                request_id=request.request_id,
                run_id=uuid4(),
                user_id=request.principal.user_id,
                organization_id=request.principal.organization_id,
                conversation_id=None,
                user_input=request.message,
                cancellation=CancellationToken(),
            ),
        )
        return await composed.execute(request, choice)

    assert asyncio.run(run()) == EXPECTED
