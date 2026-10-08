"""Unit tests for the KAI Engine orchestrator. No network and no infrastructure."""

import asyncio
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from kai_engine.context import CancellationToken, ExecutionContext
from kai_engine.contracts import (
    ContextBundle,
    EngineRequest,
    EngineResponse,
    EngineStage,
    IntentResult,
    ModelChoice,
    PlanStep,
    PlanStepKind,
    Principal,
    TaskPlan,
    ToolExecutionResult,
    VerificationResult,
)
from kai_engine.errors import (
    EngineError,
    EngineErrorKind,
    ExecutionFailureError,
    InvalidInputError,
    ProviderUnavailableError,
    UnavailableDependencyError,
    VerificationFailureError,
)
from kai_engine.orchestrator import KaiEngineOrchestrator

STAGE_ORDER = tuple(stage.value for stage in EngineStage)


def _request() -> EngineRequest:
    return EngineRequest(
        request_id=uuid4(),
        principal=Principal(user_id=uuid4(), organization_id=uuid4()),
        conversation_id=uuid4(),
        message="Inspect the pipeline",
    )


class Stages:
    """Protocol-compatible doubles that record calls and nothing else."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.agent_text = "agent-output"
        self.tool_names: list[str] = ["file_read"]
        self.broken_tool: str | None = None
        self.accept = True
        self.memory: list[UUID] = []
        self.agent_names: tuple[str, ...] = ("ResearchAgent",)
        self.fail: tuple[EngineStage, BaseException] | None = None
        self.cancel_during: EngineStage | None = None
        self.token = CancellationToken()
        self.swap_identity = False
        self.swap_bundle_org = False
        self.bad_response_id = False
        self.raise_cancelled = False
        self.model_executed = False
        self.model_text = "model-text"
        self.execute_error: BaseException | None = None
        self.execute_calls: list[str] = []
        self.candidate: str | None = None
        self.verified_with: ExecutionContext | None = None

    def _hit(self, stage: EngineStage, context: ExecutionContext) -> None:
        self.order.append(stage.value)
        if self.cancel_during is stage:
            self.token.cancel()
        if self.raise_cancelled and self.fail is None and stage is EngineStage.INTENT:
            raise asyncio.CancelledError
        if self.fail is not None and self.fail[0] is stage:
            raise self.fail[1]

    def accept_request(self, request: EngineRequest, *, context: ExecutionContext) -> EngineRequest:
        self._hit(EngineStage.INTAKE, context)
        if not self.swap_identity:
            return request
        return request.model_copy(
            update={"principal": Principal(user_id=uuid4(), organization_id=uuid4())}
        )

    async def detect(self, request: EngineRequest, *, context: ExecutionContext) -> IntentResult:
        self._hit(EngineStage.INTENT, context)
        assert context.normalized_input == request
        return IntentResult(label="unclear", confidence=0)

    async def build(
        self,
        request: EngineRequest,
        intent: IntentResult,
        *,
        context: ExecutionContext,
    ) -> ContextBundle:
        self._hit(EngineStage.CONTEXT, context)
        assert context.intent == intent
        organization_id = uuid4() if self.swap_bundle_org else request.principal.organization_id
        return ContextBundle(organization_id=organization_id, memory_ids=[], document_ids=[])

    async def plan(
        self,
        request: EngineRequest,
        bundle: ContextBundle,
        *,
        context: ExecutionContext,
    ) -> TaskPlan:
        self._hit(EngineStage.PLANNING, context)
        assert context.retrieved_context == bundle
        steps = [
            PlanStep(
                id=f"agent-{name}",
                kind=PlanStepKind.AGENT,
                description="Delegate once",
                agent_name=name,
            )
            for name in self.agent_names
        ]
        return TaskPlan(steps=steps, required_capabilities=[])

    async def select_model(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: ExecutionContext,
    ) -> ModelChoice:
        self._hit(EngineStage.MODEL_SELECTION, context)
        assert context.plan == plan
        return ModelChoice(provider_id="unconfigured", model_id="none")

    async def execute_model(self, request: EngineRequest, selection: ModelChoice) -> str:
        self.model_executed = True
        if self.execute_error is not None:
            raise self.execute_error
        assert selection.provider_id == "unconfigured"
        assert request.message != ""
        return self.model_text

    async def select_tools(self, plan: TaskPlan, *, context: ExecutionContext) -> list[str]:
        self._hit(EngineStage.TOOL_SELECTION, context)
        assert context.selected_model is not None
        assert context.selected_model.provider_id == "unconfigured"
        assert context.model_result == self.model_text
        return list(self.tool_names)

    async def execute_tool(
        self,
        principal: Principal,
        tool_name: str,
        arguments: dict[str, object],
        *,
        context: ExecutionContext,
    ) -> ToolExecutionResult:
        self._hit(EngineStage.TOOL_EXECUTION, context)
        self.execute_calls.append(tool_name)
        assert arguments == {}
        assert principal.organization_id == context.organization_id
        succeeded = tool_name != self.broken_tool
        return ToolExecutionResult(
            tool_name=tool_name,
            succeeded=succeeded,
            output="",
            error=None if succeeded else "tool reported failure",
        )

    async def run_agent(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: ExecutionContext,
    ) -> str:
        self._hit(EngineStage.AGENT_EXECUTION, context)
        assert context.selected_tools == tuple(self.tool_names)
        assert context.plan == plan
        return self.agent_text

    async def retrieve(self, request: EngineRequest, *, context: ExecutionContext) -> list[UUID]:
        self._hit(EngineStage.MEMORY_RETRIEVAL, context)
        assert context.agent_result == self.agent_text
        return list(self.memory)

    async def verify(
        self,
        request: EngineRequest,
        candidate: str,
        *,
        context: ExecutionContext,
    ) -> VerificationResult:
        self._hit(EngineStage.VERIFICATION, context)
        self.candidate = candidate
        self.verified_with = context
        assert context.memory_ids == tuple(self.memory)
        return VerificationResult(accepted=self.accept, reasons=[])

    async def compose(
        self,
        request: EngineRequest,
        candidate: str,
        verification: VerificationResult,
        *,
        context: ExecutionContext,
    ) -> EngineResponse:
        self._hit(EngineStage.RESPONSE, context)
        assert context.verification == verification
        assert candidate == self.candidate
        request_id = uuid4() if self.bad_response_id else request.request_id
        return EngineResponse(
            request_id=request_id,
            organization_id=request.principal.organization_id,
            message="",
            model_id=None,
            provider_id=None,
            verified=verification.accepted,
        )


class _Intake:
    def __init__(self, stages: Stages) -> None:
        self._stages = stages

    def accept(self, request: EngineRequest, *, context: ExecutionContext) -> EngineRequest:
        return self._stages.accept_request(request, context=context)


class _Model:
    def __init__(self, stages: Stages) -> None:
        self._stages = stages

    async def select(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: ExecutionContext,
    ) -> ModelChoice:
        return await self._stages.select_model(request, plan, context=context)

    async def execute(self, request: EngineRequest, selection: ModelChoice) -> str:
        return await self._stages.execute_model(request, selection)


class _Tools:
    def __init__(self, stages: Stages) -> None:
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
    def __init__(self, stages: Stages) -> None:
        self._stages = stages

    async def run(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: ExecutionContext,
    ) -> str:
        return await self._stages.run_agent(request, plan, context=context)


def _engine(stages: Stages) -> KaiEngineOrchestrator:
    return KaiEngineOrchestrator(
        intake=_Intake(stages),
        intent=stages,
        context=stages,
        planner=stages,
        model_router=_Model(stages),
        tool_router=_Tools(stages),
        agent=_Agent(stages),
        memory=stages,
        verifier=stages,
        responder=stages,
    )


def _run(stages: Stages, request: EngineRequest, *, run_id: UUID | None = None) -> EngineResponse:
    return asyncio.run(_engine(stages).handle(request, cancellation=stages.token, run_id=run_id))


def test_stages_run_in_documented_order_and_pass_outputs() -> None:
    stages = Stages()
    memory_id = uuid4()
    stages.memory = [memory_id]
    request = _request()
    run_id = uuid4()
    response = _run(stages, request, run_id=run_id)

    assert stages.order == list(STAGE_ORDER)
    assert stages.model_executed is True
    assert stages.candidate == "model-text"
    assert stages.verified_with is not None
    assert stages.verified_with.model_result == "model-text"
    assert stages.verified_with.agent_result == "agent-output"
    assert stages.verified_with.selected_agents == ("ResearchAgent",)
    assert stages.verified_with.tool_results is not None
    assert stages.verified_with.tool_results[0].tool_name == "file_read"
    assert stages.verified_with.memory_ids == (memory_id,)
    assert stages.verified_with.user_input == request.message
    assert stages.verified_with.run_id == run_id
    assert response.message == ""
    assert response.model_id is None
    assert response.provider_id is None
    assert response.verified is True
    assert response.request_id == request.request_id


def test_empty_stage_results_do_not_invent_a_model_response() -> None:
    stages = Stages()
    stages.agent_text = ""
    stages.tool_names = []
    stages.agent_names = ()
    stages.memory = []
    response = _run(stages, _request())

    assert stages.execute_calls == []
    assert "tool_execution" not in stages.order
    assert stages.model_executed is True
    assert stages.candidate == "model-text"
    assert stages.verified_with is not None
    assert stages.verified_with.selected_tools == ()
    assert stages.verified_with.selected_agents == ()
    assert stages.verified_with.tool_results == ()
    assert stages.verified_with.memory_ids == ()
    assert stages.verified_with.selected_model is not None
    assert response.message == ""
    assert response.model_id is None


def test_orchestrator_requires_injected_stages() -> None:
    with pytest.raises(TypeError):
        KaiEngineOrchestrator()  # type: ignore[call-arg]


@pytest.mark.parametrize("stage", list(EngineStage))
def test_each_stage_failure_stops_the_pipeline(stage: EngineStage) -> None:
    stages = Stages()
    stages.fail = (stage, RuntimeError("sk-live-secret"))
    request = _request()
    run_id = uuid4()
    with pytest.raises(EngineError) as caught:
        _run(stages, request, run_id=run_id)

    error = caught.value
    assert error.kind is EngineErrorKind.STAGE_FAILURE
    assert error.stage is stage
    assert error.request_id == request.request_id
    assert error.run_id == run_id
    assert error.organization_id == request.principal.organization_id
    assert stages.order == list(STAGE_ORDER[: STAGE_ORDER.index(stage.value) + 1])
    assert "sk-live-secret" not in str(error)
    assert "sk-live-secret" not in error.to_public_dict()["message"]
    assert "Traceback" not in error.to_public_dict()["message"]


@pytest.mark.parametrize(
    ("stage", "exc", "kind"),
    [
        (EngineStage.INTAKE, InvalidInputError(), EngineErrorKind.INVALID_INPUT),
        (
            EngineStage.MEMORY_RETRIEVAL,
            UnavailableDependencyError(),
            EngineErrorKind.UNAVAILABLE_DEPENDENCY,
        ),
        (
            EngineStage.MODEL_SELECTION,
            ProviderUnavailableError(),
            EngineErrorKind.PROVIDER_UNAVAILABLE,
        ),
        (
            EngineStage.AGENT_EXECUTION,
            ExecutionFailureError(),
            EngineErrorKind.EXECUTION_FAILURE,
        ),
        (
            EngineStage.VERIFICATION,
            VerificationFailureError(),
            EngineErrorKind.VERIFICATION_FAILURE,
        ),
    ],
)
def test_classified_stage_errors_keep_their_kind(
    stage: EngineStage,
    exc: BaseException,
    kind: EngineErrorKind,
) -> None:
    stages = Stages()
    stages.fail = (stage, exc)
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    assert caught.value.kind is kind
    assert caught.value.stage is stage
    assert caught.value.__cause__ is exc


def test_validation_error_is_invalid_input() -> None:
    stages = Stages()
    stages.fail = (
        EngineStage.INTAKE,
        ValidationError.from_exception_data("EngineRequest", []),
    )
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    assert caught.value.kind is EngineErrorKind.INVALID_INPUT
    assert caught.value.stage is EngineStage.INTAKE


def test_rejected_verification_stops_before_response() -> None:
    stages = Stages()
    stages.accept = False
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    error = caught.value
    assert error.kind is EngineErrorKind.VERIFICATION_FAILURE
    assert error.stage is EngineStage.VERIFICATION
    assert EngineStage.RESPONSE.value not in stages.order
    assert isinstance(error.context, ExecutionContext)
    assert error.context.verification is not None
    assert error.context.verification.accepted is False
    assert error.context.response is None


def test_failed_tool_stops_later_stages_and_keeps_earlier_results() -> None:
    stages = Stages()
    stages.tool_names = ["file_read", "file_search"]
    stages.broken_tool = "file_search"
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    error = caught.value
    assert error.kind is EngineErrorKind.EXECUTION_FAILURE
    assert error.stage is EngineStage.TOOL_EXECUTION
    assert error.context.tool_results is not None
    assert [item.tool_name for item in error.context.tool_results] == ["file_read", "file_search"]
    assert EngineStage.VERIFICATION.value not in stages.order


def test_context_from_another_organization_stops_the_run() -> None:
    stages = Stages()
    stages.swap_bundle_org = True
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    assert caught.value.stage is EngineStage.CONTEXT
    assert EngineStage.PLANNING.value not in stages.order


def test_intake_cannot_switch_principal() -> None:
    stages = Stages()
    stages.swap_identity = True
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    assert caught.value.stage is EngineStage.INTAKE
    assert stages.order == ["intake"]


def test_response_must_keep_request_correlation() -> None:
    stages = Stages()
    stages.bad_response_id = True
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    assert caught.value.stage is EngineStage.RESPONSE
    assert caught.value.context.response is not None


def test_cancellation_before_start_does_not_call_stages() -> None:
    stages = Stages()
    stages.token.cancel()
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    assert caught.value.kind is EngineErrorKind.CANCELLED
    assert caught.value.stage is EngineStage.INTAKE
    assert stages.order == []


def test_cancellation_between_stages_stops_the_next_stage() -> None:
    stages = Stages()
    stages.cancel_during = EngineStage.INTENT
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    assert caught.value.kind is EngineErrorKind.CANCELLED
    assert caught.value.stage is EngineStage.CONTEXT
    assert stages.order == ["intake", "intent"]


def test_model_execution_failure_stops_before_later_stages() -> None:
    stages = Stages()
    stages.execute_error = ProviderUnavailableError()
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    error = caught.value
    assert error.kind is EngineErrorKind.PROVIDER_UNAVAILABLE
    assert error.stage is EngineStage.MODEL_SELECTION
    assert error.context.selected_model is not None
    assert error.context.model_result is None
    assert EngineStage.TOOL_SELECTION.value not in stages.order


def test_cancellation_during_selection_skips_model_execution() -> None:
    stages = Stages()
    stages.cancel_during = EngineStage.MODEL_SELECTION
    with pytest.raises(EngineError) as caught:
        _run(stages, _request())
    assert caught.value.kind is EngineErrorKind.CANCELLED
    assert caught.value.stage is EngineStage.MODEL_SELECTION
    assert stages.model_executed is False
    assert EngineStage.TOOL_SELECTION.value not in stages.order


def test_task_cancellation_is_not_rewritten() -> None:
    stages = Stages()
    stages.raise_cancelled = True

    async def run() -> None:
        await _engine(stages).handle(_request(), cancellation=stages.token)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())


def test_failure_context_keeps_earlier_stage_output() -> None:
    stages = Stages()
    stages.fail = (EngineStage.PLANNING, RuntimeError("planner"))
    request = _request()
    with pytest.raises(EngineError) as caught:
        _run(stages, request)
    context = caught.value.context
    assert context.normalized_input == request
    assert context.intent is not None
    assert context.intent.label == "unclear"
    assert context.retrieved_context is not None
    assert context.plan is None
    assert context.selected_model is None
