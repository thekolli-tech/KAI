"""Thin orchestrator for the eleven KAI Engine stages.

The class holds protocol dependencies and moves values through them.
It does not classify intent, plan work, or import a model provider.
"""

import asyncio
from uuid import UUID, uuid4

from pydantic import ValidationError

from kai_engine.context import CancellationToken, ExecutionContext
from kai_engine.contracts import (
    EngineRequest,
    EngineResponse,
    EngineStage,
    PlanStepKind,
    ToolExecutionResult,
)
from kai_engine.errors import EngineError, EngineErrorKind, EngineStageError
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
        execution = ExecutionContext(
            request_id=request.request_id,
            run_id=run_id or uuid4(),
            user_id=request.principal.user_id,
            organization_id=request.principal.organization_id,
            conversation_id=request.conversation_id,
            user_input=request.message,
            cancellation=cancellation or CancellationToken(),
        )
        stage = EngineStage.INTAKE
        try:
            stage = EngineStage.INTAKE
            self._checkpoint(stage, execution)
            normalized = self._intake.accept(request, context=execution)
            self._guard_identity(normalized, execution, stage)
            execution.normalized_input = normalized

            stage = EngineStage.INTENT
            self._checkpoint(stage, execution)
            intent = await self._intent.detect(normalized, context=execution)
            execution.intent = intent

            stage = EngineStage.CONTEXT
            self._checkpoint(stage, execution)
            bundle = await self._context.build(normalized, intent, context=execution)
            if bundle.organization_id != execution.organization_id:
                raise self._error(EngineErrorKind.STAGE_FAILURE, stage, execution)
            execution.retrieved_context = bundle

            stage = EngineStage.PLANNING
            self._checkpoint(stage, execution)
            plan = await self._planner.plan(normalized, bundle, context=execution)
            execution.plan = plan
            execution.selected_agents = tuple(
                step.agent_name
                for step in plan.steps
                if step.kind is PlanStepKind.AGENT and step.agent_name is not None
            )

            stage = EngineStage.MODEL_SELECTION
            self._checkpoint(stage, execution)
            choice = await self._model_router.select(
                normalized,
                plan,
                context=execution,
            )
            execution.selected_model = choice
            self._checkpoint(stage, execution)
            execution.model_result = await self._model_router.execute(normalized, choice)

            stage = EngineStage.TOOL_SELECTION
            self._checkpoint(stage, execution)
            execution.selected_tools = tuple(
                await self._tool_router.select(plan, context=execution)
            )

            stage = EngineStage.AGENT_EXECUTION
            self._checkpoint(stage, execution)
            execution.agent_result = await self._agent.run(normalized, plan, context=execution)

            stage = EngineStage.MEMORY_RETRIEVAL
            self._checkpoint(stage, execution)
            execution.memory_ids = tuple(await self._memory.retrieve(normalized, context=execution))

            stage = EngineStage.TOOL_EXECUTION
            self._checkpoint(stage, execution)
            execution.tool_results = await self._execute_tools(normalized, execution, stage)

            stage = EngineStage.VERIFICATION
            self._checkpoint(stage, execution)
            candidate = execution.model_result
            if candidate is None:
                raise self._error(EngineErrorKind.STAGE_FAILURE, stage, execution)
            verification = await self._verifier.verify(
                normalized,
                candidate,
                context=execution,
            )
            execution.verification = verification
            if not verification.accepted:
                raise self._error(EngineErrorKind.VERIFICATION_FAILURE, stage, execution)

            stage = EngineStage.RESPONSE
            self._checkpoint(stage, execution)
            response = await self._responder.compose(
                normalized,
                candidate,
                verification,
                context=execution,
            )
            execution.response = response
            if (
                response.request_id != execution.request_id
                or response.organization_id != execution.organization_id
            ):
                raise self._error(EngineErrorKind.STAGE_FAILURE, stage, execution)
            self._checkpoint(stage, execution)
            return response
        except EngineError:
            raise
        except asyncio.CancelledError:
            raise
        except ValidationError as exc:
            raise self._error(EngineErrorKind.INVALID_INPUT, stage, execution) from exc
        except EngineStageError as exc:
            raise self._error(exc.kind, stage, execution) from exc
        except Exception as exc:
            raise self._error(EngineErrorKind.STAGE_FAILURE, stage, execution) from exc

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
