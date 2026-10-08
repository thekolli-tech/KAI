"""Typed state passed between engine stages.

None means that stage has not run. An empty tuple or string means the stage
ran and produced nothing.
"""

from dataclasses import dataclass
from uuid import UUID

from kai_engine.contracts import (
    ContextBundle,
    EngineRequest,
    EngineResponse,
    IntentResult,
    ModelChoice,
    TaskPlan,
    ToolExecutionResult,
    VerificationResult,
)


@dataclass
class CancellationToken:
    """Cooperative cancel flag shared with the caller.

    Cancelling the token stops the orchestrator before the next stage.
    It does not start a worker queue.
    """

    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


@dataclass
class ExecutionContext:
    request_id: UUID
    run_id: UUID
    user_id: UUID
    organization_id: UUID
    conversation_id: UUID | None
    user_input: str
    cancellation: CancellationToken
    normalized_input: EngineRequest | None = None
    intent: IntentResult | None = None
    retrieved_context: ContextBundle | None = None
    plan: TaskPlan | None = None
    selected_model: ModelChoice | None = None
    model_result: str | None = None
    selected_tools: tuple[str, ...] | None = None
    selected_agents: tuple[str, ...] | None = None
    tool_results: tuple[ToolExecutionResult, ...] | None = None
    agent_result: str | None = None
    memory_ids: tuple[UUID, ...] | None = None
    verification: VerificationResult | None = None
    response: EngineResponse | None = None
