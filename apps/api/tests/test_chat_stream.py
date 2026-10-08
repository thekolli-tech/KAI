"""POST /api/v1/chat/stream through the composed engine and MockModelProvider."""

import ast
import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from kai_api.app import create_app
from kai_api.composition import MOCK_MODEL_ID, MOCK_PROVIDER_ID
from kai_api.config import get_settings
from kai_engine.context import ExecutionContext
from kai_engine.contracts import EngineRequest, VerificationResult
from kai_model_runtime import GenerateRequest, MockModelProvider, ModelCapabilities, ModelCapability

USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ORG_ID = UUID("22222222-2222-4222-8222-222222222222")
TOKEN = "local-test-token"
MESSAGE = "Inspect the pipeline"
EXPECTED = f"{MOCK_PROVIDER_ID}:{MOCK_MODEL_ID}:{MESSAGE}"
REQUEST_ID = UUID("33333333-3333-4333-8333-333333333333")
CHAT = Path(__file__).resolve().parents[1] / "src" / "kai_api" / "chat.py"
SSE = Path(__file__).resolve().parents[1] / "src" / "kai_api" / "sse.py"


def _configure(monkeypatch: pytest.MonkeyPatch, *, environment: str = "development") -> None:
    monkeypatch.setenv("KAI_ENV", environment)
    monkeypatch.setenv("KAI_LOCAL_BEARER_TOKEN", TOKEN)
    monkeypatch.setenv("KAI_LOCAL_USER_ID", str(USER_ID))
    monkeypatch.setenv("KAI_LOCAL_ORGANIZATION_ID", str(ORG_ID))
    get_settings.cache_clear()


def _client(monkeypatch: pytest.MonkeyPatch, **kwargs: object) -> TestClient:
    _configure(monkeypatch)
    return TestClient(create_app(**kwargs))  # type: ignore[arg-type]


def _headers(*, token: str | None = TOKEN, request_id: UUID = REQUEST_ID) -> dict[str, str]:
    headers = {"X-Request-Id": str(request_id)}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _events(body: str) -> list[tuple[str, dict[str, object]]]:
    frames: list[tuple[str, dict[str, object]]] = []
    for block in body.split("\n\n"):
        if block.strip() == "":
            continue
        name = ""
        payload: dict[str, object] = {}
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                payload = json.loads(line.removeprefix("data: "))
        frames.append((name, payload))
    return frames


def test_stream_reconstructs_the_mock_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/api/v1/chat/stream",
        json={"message": MESSAGE},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers.get("content-encoding") in (None, "identity")
    assert response.headers["x-request-id"] == str(REQUEST_ID)
    frames = _events(response.text)
    names = [name for name, _payload in frames]
    assert names[0] == "run.started"
    assert names[-2:] == ["message.completed", "run.completed"]
    deltas = [payload["delta"] for name, payload in frames if name == "message.delta"]
    assert deltas == [EXPECTED[index : index + 16] for index in range(0, len(EXPECTED), 16)]
    assert "".join(str(delta) for delta in deltas) == EXPECTED
    completed = frames[-2][1]
    finished = frames[-1][1]
    assert completed["message"] == EXPECTED
    assert finished["message"] == EXPECTED
    assert completed["model_id"] == MOCK_MODEL_ID
    assert completed["provider_id"] == MOCK_PROVIDER_ID
    assert finished["model_id"] == MOCK_MODEL_ID
    assert finished["provider_id"] == MOCK_PROVIDER_ID
    assert completed["verified"] is True
    assert finished["verified"] is True
    assert {payload["request_id"] for _name, payload in frames} == {str(REQUEST_ID)}
    assert {payload["organization_id"] for _name, payload in frames} == {str(ORG_ID)}
    assert len({payload["run_id"] for _name, payload in frames}) == 1
    assert "run.failed" not in names
    assert "Traceback" not in response.text
    assert "intent" not in names
    schema = client.get("/api/v1/openapi.json").json()
    operation = schema["paths"]["/api/v1/chat/stream"]["post"]
    assert "text/event-stream" in operation["responses"]["200"]["content"]


def test_missing_and_invalid_tokens_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    missing = client.post(
        "/api/v1/chat/stream",
        json={"message": MESSAGE},
        headers=_headers(token=None),
    )
    invalid = client.post(
        "/api/v1/chat/stream",
        json={"message": MESSAGE},
        headers=_headers(token="wrong-token"),
    )
    for response in (missing, invalid):
        assert response.status_code == 401
        assert response.json() == {"message": "Authentication is required."}
        assert "text/event-stream" not in response.headers["content-type"]
        assert TOKEN not in response.text


def test_production_refuses_the_local_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, environment="production")
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/chat/stream",
        json={"message": MESSAGE},
        headers=_headers(),
    )
    assert response.status_code == 401
    assert TOKEN not in response.text
    assert "text/event-stream" not in response.headers["content-type"]


def test_stream_uses_the_chat_request_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    rejected = [
        {"message": ""},
        {"message": "x" * 32_001},
        {"message": MESSAGE, "conversation_id": "not-a-uuid"},
        {"message": MESSAGE, "attachment_ids": ["not-a-uuid"]},
        {"message": MESSAGE, "organization_id": str(uuid4())},
    ]
    for payload in rejected:
        response = client.post("/api/v1/chat/stream", json=payload, headers=_headers())
        assert response.status_code == 422
        assert "text/event-stream" not in response.headers["content-type"]
        assert "Traceback" not in response.text


def test_provider_unavailable_is_a_public_stream_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = MockModelProvider(
        provider_id=MOCK_PROVIDER_ID,
        model_id=MOCK_MODEL_ID,
        healthy=False,
    )
    response = _client(monkeypatch, model_provider=provider).post(
        "/api/v1/chat/stream",
        json={"message": MESSAGE},
        headers=_headers(),
    )
    assert response.status_code == 200
    frames = _events(response.text)
    names = [name for name, _payload in frames]
    assert names == ["run.started", "run.failed"]
    error = frames[-1][1]["error"]
    assert isinstance(error, dict)
    assert error["kind"] == "provider_unavailable"
    assert error["stage"] == "model_selection"
    assert error["request_id"] == str(REQUEST_ID)
    assert "Traceback" not in response.text
    assert "healthy" not in response.text


def test_execution_failure_hides_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _client(monkeypatch, model_provider=_StreamFailure()).post(
        "/api/v1/chat/stream",
        json={"message": MESSAGE},
        headers=_headers(),
    )
    assert response.status_code == 200
    frames = _events(response.text)
    assert [name for name, _payload in frames] == ["run.started", "run.failed"]
    error = frames[-1][1]["error"]
    assert isinstance(error, dict)
    assert error["kind"] == "execution_failure"
    assert error["stage"] == "model_selection"
    assert "sk-live-secret" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_stage_failure_hides_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _client(monkeypatch, verifier=_FailingVerifier()).post(
        "/api/v1/chat/stream",
        json={"message": MESSAGE},
        headers=_headers(),
    )
    assert response.status_code == 200
    frames = _events(response.text)
    names = [name for name, _payload in frames]
    assert "message.delta" in names
    assert "message.completed" not in names
    assert names[-1] == "run.failed"
    error = frames[-1][1]["error"]
    assert isinstance(error, dict)
    assert error["kind"] == "stage_failure"
    assert error["stage"] == "verification"
    assert "sk-live-secret" not in response.text
    assert "Traceback" not in response.text


def test_rejected_verification_does_not_complete_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _client(monkeypatch, verifier=_RejectingVerifier()).post(
        "/api/v1/chat/stream",
        json={"message": MESSAGE},
        headers=_headers(),
    )
    frames = _events(response.text)
    names = [name for name, _payload in frames]
    assert "message.delta" in names
    assert "run.completed" not in names
    error = frames[-1][1]["error"]
    assert isinstance(error, dict)
    assert error["kind"] == "verification_failure"


def test_unknown_failure_is_a_generic_stream_event(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    client = TestClient(create_app())
    client.app.state.engine = _ExplodingEngine()
    response = client.post(
        "/api/v1/chat/stream",
        json={"message": MESSAGE},
        headers=_headers(),
    )
    assert response.status_code == 200
    frames = _events(response.text)
    assert [name for name, _payload in frames] == ["run.failed"]
    failed = frames[0][1]
    assert failed["request_id"] == str(REQUEST_ID)
    assert failed["organization_id"] == str(ORG_ID)
    assert failed["error"] == {"message": "The request could not be completed."}
    assert "sk-live-secret" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_client_disconnect_closes_the_provider_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Close the provider when the ASGI client disconnects.

    The TestClient transport buffers the body and emits disconnect only after
    the app finishes, so this test drives the ASGI app directly.
    """

    _configure(monkeypatch)
    provider = _PausingProvider()
    app = create_app(model_provider=provider)
    body = json.dumps({"message": MESSAGE}).encode()

    async def drive() -> tuple[int, dict[str, str], bytes]:
        sent_body = False
        delta_seen = asyncio.Event()
        collected = bytearray()
        status = 0
        headers: dict[str, str] = {}

        async def receive() -> dict[str, object]:
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            await delta_seen.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict[str, object]) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])  # type: ignore[arg-type]
                raw_headers = message["headers"]
                assert isinstance(raw_headers, list)
                headers.update({key.decode().lower(): value.decode() for key, value in raw_headers})
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                assert isinstance(chunk, bytes)
                collected.extend(chunk)
                if b"event: message.delta" in chunk:
                    delta_seen.set()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/chat/stream",
            "raw_path": b"/api/v1/chat/stream",
            "query_string": b"",
            "headers": [
                (b"host", b"testserver"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"authorization", f"Bearer {TOKEN}".encode()),
                (b"x-request-id", str(REQUEST_ID).encode()),
            ],
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
        }
        await app(scope, receive, send)
        return status, headers, bytes(collected)

    status, headers, payload = asyncio.run(drive())
    assert status == 200
    assert headers["content-type"].startswith("text/event-stream")
    assert b"event: message.delta" in payload
    assert b"Traceback" not in payload
    assert provider.closed is True
    assert provider.chunks == 1


def test_route_does_not_import_the_mock_provider() -> None:
    for path in (CHAT, SSE):
        text = path.read_text(encoding="utf-8")
        assert "MockModelProvider" not in text
        tree = ast.parse(text)
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert all(not module.startswith("kai_model_runtime") for module in modules)


class _StreamFailure:
    provider_id = MOCK_PROVIDER_ID

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            provider_id=MOCK_PROVIDER_ID,
            model_id=MOCK_MODEL_ID,
            capabilities=(ModelCapability.TEXT, ModelCapability.STREAM),
            max_context_tokens=32,
        )

    async def health_check(self) -> bool:
        return True

    async def generate(self, request: GenerateRequest):
        del request
        raise AssertionError("the stream route calls stream")

    async def stream(self, request: GenerateRequest):
        del request
        if True:
            raise RuntimeError("sk-live-secret")
        yield ""


class _PausingProvider:
    provider_id = MOCK_PROVIDER_ID

    def __init__(self) -> None:
        self.closed = False
        self.chunks = 0

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            provider_id=MOCK_PROVIDER_ID,
            model_id=MOCK_MODEL_ID,
            capabilities=(ModelCapability.TEXT, ModelCapability.STREAM),
            max_context_tokens=32,
        )

    async def health_check(self) -> bool:
        return True

    async def generate(self, request: GenerateRequest):
        del request
        raise AssertionError("the stream route calls stream")

    async def stream(self, request: GenerateRequest):
        del request
        try:
            self.chunks += 1
            yield "one"
            await asyncio.Event().wait()
            self.chunks += 1
            yield "two"
        finally:
            self.closed = True


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


class _RejectingVerifier:
    async def verify(
        self,
        request: EngineRequest,
        candidate: str,
        *,
        context: ExecutionContext,
    ) -> VerificationResult:
        del request, candidate, context
        return VerificationResult(accepted=False, reasons=[])


class _ExplodingEngine:
    def handle_stream(
        self,
        request: EngineRequest,
        *,
        cancellation: object = None,
        run_id: object = None,
    ):
        del request, cancellation, run_id

        async def _events():
            raise RuntimeError("sk-live-secret")
            yield None

        return _events()
