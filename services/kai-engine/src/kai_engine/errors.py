"""Typed failures for the KAI Engine orchestrator.

Public messages stay stable. The original exception remains on ``__cause__``
for server logs and is not included in the public message.
"""

from enum import StrEnum
from uuid import UUID

from kai_engine.context import ExecutionContext
from kai_engine.contracts import EngineStage


class EngineErrorKind(StrEnum):
    INVALID_INPUT = "invalid_input"
    UNAVAILABLE_DEPENDENCY = "unavailable_dependency"
    STAGE_FAILURE = "stage_failure"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    EXECUTION_FAILURE = "execution_failure"
    VERIFICATION_FAILURE = "verification_failure"
    CANCELLED = "cancelled"


class EngineStageError(Exception):
    """A stage reports a classified failure without choosing the public wording."""

    kind: EngineErrorKind

    def __init__(self) -> None:
        super().__init__(self.kind.value)


class InvalidInputError(EngineStageError):
    kind = EngineErrorKind.INVALID_INPUT


class UnavailableDependencyError(EngineStageError):
    kind = EngineErrorKind.UNAVAILABLE_DEPENDENCY


class ProviderUnavailableError(EngineStageError):
    kind = EngineErrorKind.PROVIDER_UNAVAILABLE


class ExecutionFailureError(EngineStageError):
    kind = EngineErrorKind.EXECUTION_FAILURE


class VerificationFailureError(EngineStageError):
    kind = EngineErrorKind.VERIFICATION_FAILURE


def public_message(kind: EngineErrorKind, stage: EngineStage) -> str:
    sentences = {
        EngineErrorKind.INVALID_INPUT: "The request is invalid.",
        EngineErrorKind.UNAVAILABLE_DEPENDENCY: "A required dependency is unavailable.",
        EngineErrorKind.STAGE_FAILURE: "The stage failed.",
        EngineErrorKind.PROVIDER_UNAVAILABLE: "The model provider is unavailable.",
        EngineErrorKind.EXECUTION_FAILURE: "Execution failed.",
        EngineErrorKind.VERIFICATION_FAILURE: "Verification rejected the result.",
        EngineErrorKind.CANCELLED: "The run was cancelled.",
    }
    return f"{sentences[kind]} Stage: {stage.value}."


class EngineError(Exception):
    """Pipeline failure. ``str(error)`` is safe to return from an API."""

    def __init__(
        self,
        *,
        kind: EngineErrorKind,
        stage: EngineStage,
        request_id: UUID,
        run_id: UUID,
        organization_id: UUID,
        context: ExecutionContext,
    ) -> None:
        self.kind = kind
        self.stage = stage
        self.request_id = request_id
        self.run_id = run_id
        self.organization_id = organization_id
        self.context = context
        self.public_message = public_message(kind, stage)
        super().__init__(self.public_message)

    def to_public_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "stage": self.stage.value,
            "request_id": str(self.request_id),
            "run_id": str(self.run_id),
            "organization_id": str(self.organization_id),
            "message": self.public_message,
        }
