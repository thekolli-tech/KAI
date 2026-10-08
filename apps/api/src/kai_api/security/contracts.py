"""Authentication, authorization, rate limiting, and audit ports.

Phase 1 does not attach these to routes. Health stays public. Product
routes must depend on them before they are added, and must fail closed.
"""

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from kai_engine.contracts import AuthorizationDecision, Principal


class RequestCredentials(BaseModel):
    model_config = ConfigDict(frozen=True)

    scheme: str = Field(pattern="^(bearer|session)$")
    token: str = Field(min_length=1, max_length=4096)


class RateLimitDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    limit: int = Field(ge=0)
    remaining: int = Field(ge=0)
    retry_after_seconds: int = Field(ge=0)


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    actor_user_id: UUID | None
    action: str = Field(min_length=1, max_length=120)
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class Authenticator(Protocol):
    async def authenticate(self, credentials: RequestCredentials) -> Principal:
        """Resolve a principal from server-side credentials.

        The organization id on the principal must come from a membership,
        not from a caller-supplied header.
        """


class Authorizer(Protocol):
    async def authorize(
        self,
        principal: Principal,
        *,
        action: str,
        organization_id: UUID,
    ) -> AuthorizationDecision:
        """Allow an action only inside the principal's organization."""


class RateLimiter(Protocol):
    async def check(
        self,
        *,
        organization_id: UUID,
        subject: str,
        action: str,
    ) -> RateLimitDecision:
        """Decide whether this subject may perform the action now.

        The later implementation uses Redis. This phase has no limiter that
        silently allows traffic.
        """


class AuditLogger(Protocol):
    async def write(self, event: AuditEvent) -> None:
        """Append an audit event. Updates and deletes are not part of the port."""
