from uuid import uuid4

from kai_api.security import organization_boundary
from kai_engine.contracts import Principal


def test_same_organization_is_allowed() -> None:
    organization_id = uuid4()
    principal = Principal(user_id=uuid4(), organization_id=organization_id)
    decision = organization_boundary(principal, organization_id)
    assert decision.allowed is True


def test_cross_organization_access_is_denied() -> None:
    principal = Principal(user_id=uuid4(), organization_id=uuid4())
    decision = organization_boundary(principal, uuid4())
    assert decision.allowed is False
    assert decision.reason == "Organization boundary"
