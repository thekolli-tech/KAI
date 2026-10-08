"""Organization separation.

The authenticated principal's organization comes from a membership lookup
on the server. A client-supplied organization id is never trusted on its own.
"""

from uuid import UUID

from kai_engine.contracts import AuthorizationDecision, Principal


def organization_boundary(principal: Principal, organization_id: UUID) -> AuthorizationDecision:
    if principal.organization_id != organization_id:
        return AuthorizationDecision(allowed=False, reason="Organization boundary")
    return AuthorizationDecision(allowed=True, reason="Same organization")
