"""POST /api/v1/chat through the composed engine and MockModelProvider."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from kai_api.app import create_app
from kai_api.composition import MOCK_MODEL_ID, MOCK_PROVIDER_ID
from kai_api.config import get_settings
from kai_api.model_router import RegisteredModelRouter
from kai_engine.context import ExecutionContext
from kai_engine.contracts import EngineRequest, VerificationResult
from kai_engine.orchestrator import KaiEngineOrchestrator
from kai_model_runtime import (
    GenerateRequest,
    MockModelProvider,
    ModelCapabilities,
    ModelCapability,
    ModelOutput,
)

USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ORG_ID = UUID("22222222-2222-4222-8222-222222222222")
TOKEN = "local-test-token"
MESSAGE = "Inspect the pipeline"
EXPECTED = f"{MOCK_PROVIDER_ID}:{MOCK_MODEL_ID}:{MESSAGE}"


def _configure(monkeypatch: pytest.MonkeyPatch, *, environment: str = "development") -> None:
    monkeypatch.setenv("KAI_ENV", environment)
    monkeypatch.setenv("KAI_LOCAL_BEARER_TOKEN", TOKEN)
    monkeypatch.setenv("KAI_LOCAL_USER_ID", str(USER_ID))
    monkeypatch.setenv("KAI_LOCAL_ORGANIZATION_ID", str(ORG_ID))
    get_settings.cache_clear()


def _client(monkeypatch: pytest.MonkeyPatch, **kwargs: object) -> TestClient:
    _configure(monkeypatch)
    return TestClient(create_app(**kwargs))  # type: ignore[arg-type]


def _post(client: TestClient, payload: dict[str, object] | None = None, *, token: str = TOKEN):
    body = {"message": MESSAGE} if payload is None else payload
    return client.post(
        "/api/v1/chat",
        json=body,
        headers={"Authorization": f"Bearer {token}", "X-Request-Id": str(uuid4())},
    )


def test_chat_returns_the_mock_model_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    app = create_app()
    client = TestClient(app)
    request_id = UUID("33333333-3333-4333-8333-333333333333")
    response = client.post(
        "/api/v1/chat",
        json={"message": MESSAGE},
        headers={"Authorization": f"Bearer {TOKEN}", "X-Request-Id": str(request_id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "request_id": str(request_id),
        "organization_id": str(ORG_ID),
        "message": EXPECTED,
        "model_id": MOCK_MODEL_ID,
        "provider_id": MOCK_PROVIDER_ID,
        "verified": True,
    }
    assert isinstance(app.state.engine, KaiEngineOrchestrator)
    assert isinstance(app.state.model_router, RegisteredModelRouter)
    assert "Traceback" not in response.text
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["checks"]["model_runtime"] == "mock"
    assert health.json()["checks"]["engine"] == "interface_only"


def test_chat_response_uses_the_engine_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _post(_client(monkeypatch))
    assert response.status_code == 200
    assert set(response.json()) == {
        "request_id",
        "organization_id",
        "message",
        "model_id",
        "provider_id",
        "verified",
    }


def test_empty_and_foreign_fields_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    assert _post(client, {"message": ""}).status_code == 422
    assert client.post("/api/v1/chat", json={}).status_code == 422
    foreign = _post(client, {"message": MESSAGE, "organization_id": str(uuid4())})
    assert foreign.status_code == 422


def test_missing_credential_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    response = client.post("/api/v1/chat", json={"message": MESSAGE})
    assert response.status_code == 401
    assert response.json() == {"message": "Authentication is required."}
    assert TOKEN not in response.text


def test_production_refuses_the_local_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, environment="production")
    client = TestClient(create_app())
    response = _post(client)
    assert response.status_code == 401
    assert TOKEN not in response.text


def test_provider_unavailable_is_a_stable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = MockModelProvider(
        provider_id=MOCK_PROVIDER_ID,
        model_id=MOCK_MODEL_ID,
        healthy=False,
    )
    response = _post(_client(monkeypatch, model_provider=provider))
    assert response.status_code == 503
    body = response.json()
    assert body["kind"] == "provider_unavailable"
    assert body["stage"] == "model_selection"
    assert body["organization_id"] == str(ORG_ID)
    assert "Traceback" not in response.text
    assert "healthy" not in body["message"]


def test_model_execution_failure_hides_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _post(_client(monkeypatch, model_provider=_FailingProvider()))
    assert response.status_code == 502
    body = response.json()
    assert body["kind"] == "execution_failure"
    assert body["stage"] == "model_selection"
    assert "sk-live-secret" not in response.text
    assert "Traceback" not in response.text


def test_engine_stage_failure_hides_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _post(_client(monkeypatch, verifier=_FailingVerifier()))
    assert response.status_code == 500
    body = response.json()
    assert body["kind"] == "stage_failure"
    assert body["stage"] == "verification"
    assert "sk-live-secret" not in response.text
    assert "Traceback" not in response.text


def test_unknown_failure_is_a_generic_500(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.app.state.authenticator = _ExplodingAuthenticator()
    response = _post(client)
    assert response.status_code == 500
    assert response.json() == {"message": "The request could not be completed."}
    assert "sk-live-secret" not in response.text
    assert "Traceback" not in response.text


class _FailingProvider:
    provider_id = MOCK_PROVIDER_ID

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            provider_id=MOCK_PROVIDER_ID,
            model_id=MOCK_MODEL_ID,
            capabilities=(ModelCapability.TEXT,),
            max_context_tokens=32,
        )

    async def health_check(self) -> bool:
        return True

    async def generate(self, request: GenerateRequest) -> ModelOutput:
        del request
        raise RuntimeError("sk-live-secret")

    async def stream(self, request: GenerateRequest):
        del request
        yield ""


class _FailingVerifier:
    async def verify(
        self,
        request: EngineRequest,
        candidate: str,
        *,
        context: ExecutionContext,
    ) -> VerificationResult:
        del request, candidate, context
        raise RuntimeError("sk-live-secret")


class _ExplodingAuthenticator:
    async def authenticate(self, credentials: object) -> object:
        del credentials
        raise RuntimeError("sk-live-secret")
