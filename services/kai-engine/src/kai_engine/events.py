"""Public run events. These are not SSE frames and do not name internal stages."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RunEventType(StrEnum):
    STARTED = "run.started"
    DELTA = "message.delta"
    MESSAGE_COMPLETED = "message.completed"
    COMPLETED = "run.completed"
    FAILED = "run.failed"


class RunEvent(BaseModel):
    """Correlation fields are always set. Other fields appear only when they apply."""

    model_config = ConfigDict(frozen=True)

    type: RunEventType
    request_id: UUID
    run_id: UUID
    organization_id: UUID
    delta: str | None = None
    message: str | None = None
    model_id: str | None = None
    provider_id: str | None = None
    verified: bool | None = None
    error: dict[str, str] | None = None
