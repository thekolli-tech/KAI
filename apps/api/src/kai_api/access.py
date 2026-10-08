"""Local access check for chat.

This is not a production authenticator. The principal comes from server
configuration. A request body or header cannot choose the organization.
Production refuses every credential.
"""

import secrets
from uuid import UUID

from kai_api.config import Settings
from kai_api.security.contracts import RequestCredentials
from kai_api.security.tenancy import organization_boundary
from kai_api.status import EnvironmentName
from kai_engine.contracts import AuthorizationDecision, Principal


class AuthenticationFailed(Exception):
    """The credential is missing, unknown, or disabled."""


class LocalDevelopmentAuthenticator:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.kai_local_bearer_token
        self._principal = _principal(settings)

    async def authenticate(self, credentials: RequestCredentials) -> Principal:
        principal = self._principal
        if principal is None or self._token == "":
            raise AuthenticationFailed
        if credentials.scheme != "bearer":
            raise AuthenticationFailed
        if not secrets.compare_digest(credentials.token, self._token):
            raise AuthenticationFailed
        return principal


class BoundaryAuthorizer:
    async def authorize(
        self,
        principal: Principal,
        *,
        action: str,
        organization_id: UUID,
    ) -> AuthorizationDecision:
        del action
        return organization_boundary(principal, organization_id)


def _principal(settings: Settings) -> Principal | None:
    if settings.kai_env is EnvironmentName.PRODUCTION:
        return None
    if settings.kai_local_bearer_token.strip() == "":
        return None
    try:
        user_id = UUID(settings.kai_local_user_id)
        organization_id = UUID(settings.kai_local_organization_id)
    except ValueError:
        return None
    return Principal(user_id=user_id, organization_id=organization_id)
