"""Thin orchestrator for the eleven KAI Engine stages.

The class holds protocol dependencies and moves values through them.
It does not classify intent, plan work, or import a model provider.
"""

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from pydantic import ValidationError

from kai_engine.context import CancellationToken, ExecutionContext
from kai_engine.contracts import (
    EngineRequest,
    EngineResponse,
    EngineStage,
    ModelChoice,
    PlanStepKind,
    ToolExecutionResult,
)
from kai_engine.errors import EngineError, EngineErrorKind, EngineStageError
from kai_engine.events import RunEvent, RunEventType
from kai_engine.interfaces import (
    AgentEngine,
    ContextEngine,
    IntentEngine,
    MemoryEngine,
    ModelRouter,
    PlanningEngine,
    RequestIntake,
    ResponseEngine,
    ToolRouter,
    VerificationEngine,
)


class _Cursor:
    def __init__(self) -> None:
        self.stage = EngineStage.INTAKE


class KaiEngineOrchestrator:
    """Compose the stage protocols. Construct it with explicit dependencies."""

    def __init__(
        self,
        *,
        intake: RequestIntake,
        intent: IntentEngine,
        context: ContextEngine,
        planner: PlanningEngine,
        model_router: ModelRouter,
        tool_router: ToolRouter,
        agent: AgentEngine,
        memory: MemoryEngine,
        verifier: VerificationEngine,
        responder: ResponseEngine,
    ) -> None:
        self._intake = intake
        self._intent = intent
        self._context = context
        self._planner = planner
        self._model_router = model_router
        self._tool_router = tool_router
        self._agent = agent
        self._memory = memory
        self._verifier = verifier
        self._responder = responder

    async def handle(
        self,
        request: EngineRequest,
        *,
        cancellation: CancellationToken | None = None,
        run_id: UUID | None = None,
    ) -> EngineResponse:
        execution = self._begin(request, cancellation, run_id)
        cursor = _Cursor()
        try:
            normalized, choice = await self._prepare(request, execution, cursor)
            cursor.stage = EngineStage.MODEL_SELECTION
            self._checkpoint(cursor.stage, execution)
            execution.model_result = await self._model_router.execute(normalized, choice)
            return await self._finish(normalized, execution, cursor)
        except EngineError:
            raise
        except asyncio.CancelledError:
            raise
        except ValidationError as exc:
            raise self._error(EngineErrorKind.INVALID_INPUT, cursor.stage, execution) from exc
        except EngineStageError as exc:
            raise self._error(exc.kind, cursor.stage, execution) from exc
        except Exception as exc:
            raise self._error(EngineErrorKind.STAGE_FAILURE, cursor.stage, execution) from exc

    async def handle_stream(
        self,
        request: EngineRequest,
        *,
        cancellation: CancellationToken | None = None,
        run_id: UUID | None = None,
    ) -> AsyncIterator[RunEvent]:
        execution = self._begin(request, cancellation, run_id)
        cursor = _Cursor()
        try:
            yield self._event(RunEventType.STARTED, execution)
            normalized, choice = await self._prepare(request, execution, cursor)
            cursor.stage = EngineStage.MODEL_SELECTION
            self._checkpoint(cursor.stage, execution)
            parts: list[str] = []
            async for chunk in self._model_router.stream(normalized, choice):
                self._checkpoint(cursor.stage, execution)
                parts.append(chunk)
                execution.model_result = "".join(parts)
                yield self._event(RunEventType.DELTA, execution, delta=chunk)
            if execution.model_result is None:
                execution.model_result = ""
            response = await self._finish(normalized, execution, cursor)
            yield self._event(
                RunEventType.MESSAGE_COMPLETED,
                execution,
                message=response.message,
                model_id=response.model_id,
                provider_id=response.provider_id,
                verified=response.verified,
            )
            yield self._event(
                RunEventType.COMPLETED,
                execution,
                message=response.message,
                model_id=response.model_id,
                provider_id=response.provider_id,
                verified=response.verified,
            )
        except EngineError as exc:
            yield self._failed(exc)
        except asyncio.CancelledError:
            raise
        except ValidationError:
            error = self._error(EngineErrorKind.INVALID_INPUT, cursor.stage, execution)
            yield self._failed(error)
        except EngineStageError as exc:
            yield self._failed(self._error(exc.kind, cursor.stage, execution))
        except Exception:
            error = self._error(EngineErrorKind.STAGE_FAILURE, cursor.stage, execution)
            yield self._failed(error)

    def _begin(
        self,
        request: EngineRequest,
        cancellation: CancellationToken | None,
        run_id: UUID | None,
    ) -> ExecutionContext:
        return ExecutionContext(
            request_id=request.request_id,
            run_id=run_id or uuid4(),
            user_id=request.principal.user_id,
            organization_id=request.principal.organization_id,
            conversation_id=request.conversation_id,
            user_input=request.message,
            cancellation=cancellation or CancellationToken(),
        )

    async def _prepare(
        self,
        request: EngineRequest,
        execution: ExecutionContext,
        cursor: _Cursor,
    ) -> tuple[EngineRequest, ModelChoice]:
        cursor.stage = EngineStage.INTAKE
        self._checkpoint(cursor.stage, execution)
        normalized = self._intake.accept(request, context=execution)
        self._guard_identity(normalized, execution, cursor.stage)
        execution.normalized_input = normalized

        cursor.stage = EngineStage.INTENT
        self._checkpoint(cursor.stage, execution)
        intent = await self._intent.detect(normalized, context=execution)
        execution.intent = intent

        cursor.stage = EngineStage.CONTEXT
        self._checkpoint(cursor.stage, execution)
        bundle = await self._context.build(normalized, intent, context=execution)
        if bundle.organization_id != execution.organization_id:
            raise self._error(EngineErrorKind.STAGE_FAILURE, cursor.stage, execution)
        execution.retrieved_context = bundle

        cursor.stage = EngineStage.PLANNING
        self._checkpoint(cursor.stage, execution)
        plan = await self._planner.plan(normalized, bundle, context=execution)
        execution.plan = plan
        execution.selected_agents = tuple(
            step.agent_name
            for step in plan.steps
            if step.kind is PlanStepKind.AGENT and step.agent_name is not None
        )

        cursor.stage = EngineStage.MODEL_SELECTION
        self._checkpoint(cursor.stage, execution)
        choice = await self._model_router.select(normalized, plan, context=execution)
        execution.selected_model = choice
        return normalized, choice

    async def _finish(
        self,
        request: EngineRequest,
        execution: ExecutionContext,
        cursor: _Cursor,
    ) -> EngineResponse:
        plan = execution.plan
        if plan is None or execution.model_result is None:
            raise self._error(EngineErrorKind.STAGE_FAILURE, cursor.stage, execution)

        cursor.stage = EngineStage.TOOL_SELECTION
        self._checkpoint(cursor.stage, execution)
        execution.selected_tools = tuple(await self._tool_router.select(plan, context=execution))

        cursor.stage = EngineStage.AGENT_EXECUTION
        self._checkpoint(cursor.stage, execution)
        execution.agent_result = await self._agent.run(request, plan, context=execution)

        cursor.stage = EngineStage.MEMORY_RETRIEVAL
        self._checkpoint(cursor.stage, execution)
        execution.memory_ids = tuple(await self._memory.retrieve(request, context=execution))

        cursor.stage = EngineStage.TOOL_EXECUTION
        self._checkpoint(cursor.stage, execution)
        execution.tool_results = await self._execute_tools(request, execution, cursor.stage)

        cursor.stage = EngineStage.VERIFICATION
        self._checkpoint(cursor.stage, execution)
        candidate = execution.model_result
        verification = await self._verifier.verify(request, candidate, context=execution)
        execution.verification = verification
        if not verification.accepted:
            raise self._error(EngineErrorKind.VERIFICATION_FAILURE, cursor.stage, execution)

        cursor.stage = EngineStage.RESPONSE
        self._checkpoint(cursor.stage, execution)
        response = await self._responder.compose(
            request,
            candidate,
            verification,
            context=execution,
        )
        execution.response = response
        if (
            response.request_id != execution.request_id
            or response.organization_id != execution.organization_id
        ):
            raise self._error(EngineErrorKind.STAGE_FAILURE, cursor.stage, execution)
        self._checkpoint(cursor.stage, execution)
        return response

    async def _execute_tools(
        self,
        request: EngineRequest,
        execution: ExecutionContext,
        stage: EngineStage,
    ) -> tuple[ToolExecutionResult, ...]:
        names = execution.selected_tools or ()
        results: list[ToolExecutionResult] = []
        for name in names:
            self._checkpoint(stage, execution)
            result = await self._tool_router.execute(
                request.principal,
                name,
                {},
                context=execution,
            )
            results.append(result)
            execution.tool_results = tuple(results)
            if not result.succeeded:
                raise self._error(EngineErrorKind.EXECUTION_FAILURE, stage, execution)
        return tuple(results)

    def _guard_identity(
        self,
        request: EngineRequest,
        execution: ExecutionContext,
        stage: EngineStage,
    ) -> None:
        principal = request.principal
        if (
            principal.user_id != execution.user_id
            or principal.organization_id != execution.organization_id
        ):
            raise self._error(EngineErrorKind.STAGE_FAILURE, stage, execution)

    def _checkpoint(self, stage: EngineStage, execution: ExecutionContext) -> None:
        if execution.cancellation.cancelled:
            raise self._error(EngineErrorKind.CANCELLED, stage, execution)

    def _error(
        self,
        kind: EngineErrorKind,
        stage: EngineStage,
        execution: ExecutionContext,
    ) -> EngineError:
        return EngineError(
            kind=kind,
            stage=stage,
            request_id=execution.request_id,
            run_id=execution.run_id,
            organization_id=execution.organization_id,
            context=execution,
        )

    def _event(
        self,
        event_type: RunEventType,
        execution: ExecutionContext,
        *,
        delta: str | None = None,
        message: str | None = None,
        model_id: str | None = None,
        provider_id: str | None = None,
        verified: bool | None = None,
    ) -> RunEvent:
        return RunEvent(
            type=event_type,
            request_id=execution.request_id,
            run_id=execution.run_id,
            organization_id=execution.organization_id,
            delta=delta,
            message=message,
            model_id=model_id,
            provider_id=provider_id,
            verified=verified,
        )

    def _failed(self, error: EngineError) -> RunEvent:
        return RunEvent(
            type=RunEventType.FAILED,
            request_id=error.request_id,
            run_id=error.run_id,
            organization_id=error.organization_id,
            error=error.to_public_dict(),
        )
