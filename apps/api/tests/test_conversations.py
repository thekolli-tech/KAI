"""Conversation and message persistence through PostgreSQL."""

import ast
import asyncio
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from kai_api.app import create_app
from kai_api.config import get_settings
from kai_api.persistence import ConversationStore
from kai_engine.context import ExecutionContext
from kai_engine.contracts import EngineRequest, VerificationResult
from kai_model_runtime import GenerateRequest, ModelCapabilities, ModelCapability

SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "infrastructure"
    / "postgres"
    / "migrations"
    / "001_initial.sql"
)
DEFAULT_URL = "postgresql://kai:kai-local-password@127.0.0.1:5432/kai_test"
ORG_A = UUID("22222222-2222-4222-8222-222222222222")
USER_A = UUID("11111111-1111-4111-8111-111111111111")
ORG_B = UUID("55555555-5555-4555-8555-555555555555")
USER_B = UUID("66666666-6666-4666-8666-666666666666")
TOKEN = "local-test-token"
PERSISTENCE = Path(__file__).resolve().parents[1] / "src" / "kai_api" / "persistence.py"
CONVERSATIONS = Path(__file__).resolve().parents[1] / "src" / "kai_api" / "conversations.py"


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.environ.get("KAI_TEST_DATABASE_URL", DEFAULT_URL).strip()
    with psycopg.connect(url, autocommit=True) as conn:
        found = conn.execute("SELECT to_regclass('public.conversations')").fetchone()
        if found is None or found[0] is None:
            script = SCHEMA.read_text(encoding="utf-8")
            with psycopg.ClientCursor(conn) as cursor:
                cursor.execute(script)
    return url


@pytest.fixture(autouse=True)
def empty_transcripts(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE messages, conversations CASCADE")


def test_conversation_is_owned_by_the_authenticated_organization(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
) -> None:
    client = _client(monkeypatch, database_url)
    rejected = client.post(
        "/api/v1/conversations",
        json={"organization_id": str(ORG_B)},
        headers=_headers(),
    )
    assert rejected.status_code == 422
    assert str(ORG_B) not in rejected.text
    created = client.post("/api/v1/conversations", headers=_headers())
    assert created.status_code == 201
    body = created.json()
    assert UUID(body["id"])
    assert body["title"] == "New chat"
    assert body["updatedAt"]
    stored = _owner(database_url, body["id"])
    assert stored == ORG_A


def test_unknown_conversation_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
) -> None:
    client = _client(monkeypatch, database_url)
    missing = uuid4()
    response = client.get(f"/api/v1/conversations/{missing}", headers=_headers())
    assert response.status_code == 404
    assert response.json() == {"message": "That conversation is not available."}
    assert _rows(database_url, missing) == []


def test_other_organization_cannot_read_or_append(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
) -> None:
    owner = _client(monkeypatch, database_url)
    created = owner.post("/api/v1/conversations", headers=_headers())
    conversation_id = created.json()["id"]
    sent = owner.post(
        "/api/v1/chat/stream",
        json={"message": "Hello KAI", "conversation_id": conversation_id},
        headers=_headers(),
    )
    assert sent.status_code == 200
    intruder = _client(
        monkeypatch,
        database_url,
        organization_id=ORG_B,
        user_id=USER_B,
    )
    listed = intruder.get("/api/v1/conversations", headers=_headers())
    assert listed.status_code == 200
    assert listed.json()["conversations"] == []
    hidden = intruder.get(f"/api/v1/conversations/{conversation_id}", headers=_headers())
    assert hidden.status_code == 404
    assert "Hello KAI" not in hidden.text
    appended = intruder.post(
        "/api/v1/chat/stream",
        json={"message": "cross-org write", "conversation_id": conversation_id},
        headers=_headers(),
    )
    assert appended.status_code == 404
    assert "cross-org write" not in appended.text
    roles = [role for role, _content in _rows(database_url, conversation_id)]
    assert roles == ["user", "assistant"]
    contents = [content for _role, content in _rows(database_url, conversation_id)]
    assert "cross-org write" not in contents


def test_stream_persists_one_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
) -> None:
    client = _client(monkeypatch, database_url)
    conversation_id = client.post("/api/v1/conversations", headers=_headers()).json()["id"]
    first = client.post(
        "/api/v1/chat/stream",
        json={"message": "Hello KAI", "conversation_id": conversation_id},
        headers=_headers(),
    )
    assert first.status_code == 200
    frames = _events(first.text)
    names = [name for name, _payload in frames]
    assert names[0] == "run.started"
    assert "message.delta" in names
    assert names[-2:] == ["message.completed", "run.completed"]
    deltas = [str(payload["delta"]) for name, payload in frames if name == "message.delta"]
    assert "".join(deltas) == "mock:mock-text:Hello KAI"
    assert {payload["organization_id"] for _name, payload in frames} == {str(ORG_A)}
    assert all(payload["request_id"] and payload["run_id"] for _name, payload in frames)
    second = client.post(
        "/api/v1/chat/stream",
        json={"message": "Second turn", "conversation_id": conversation_id},
        headers=_headers(),
    )
    assert second.status_code == 200
    detail = client.get(f"/api/v1/conversations/{conversation_id}", headers=_headers())
    assert detail.status_code == 200
    body = detail.json()
    assert body["title"] == "Hello KAI"
    assert [(item["role"], item["content"], item["status"]) for item in body["messages"]] == [
        ("user", "Hello KAI", "completed"),
        ("assistant", "mock:mock-text:Hello KAI", "completed"),
        ("user", "Second turn", "completed"),
        ("assistant", "mock:mock-text:Second turn", "completed"),
    ]
    assert [role for role, _content in _rows(database_url, conversation_id)].count("assistant") == 2


def test_failed_and_cancelled_runs_do_not_store_a_completed_assistant(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
) -> None:
    _configure(monkeypatch, database_url)
    failed = TestClient(create_app(verifier=_RejectingVerifier()))
    conversation_id = failed.post("/api/v1/conversations", headers=_headers()).json()["id"]
    response = failed.post(
        "/api/v1/chat/stream",
        json={"message": "Hello KAI", "conversation_id": conversation_id},
        headers=_headers(),
    )
    assert response.status_code == 200
    names = [name for name, _payload in _events(response.text)]
    assert names[-1] == "run.failed"
    assert "run.completed" not in names
    assert "sk-live-secret" not in response.text
    assert _rows(database_url, conversation_id) == [("user", "Hello KAI")]

    provider = _PausingProvider()
    app = create_app(model_provider=provider)
    conversation_id = TestClient(app).post("/api/v1/conversations", headers=_headers()).json()["id"]
    status, payload = asyncio.run(_disconnect(app, conversation_id))
    assert status == 200
    assert b"event: message.delta" in payload
    assert b"event: run.completed" not in payload
    assert provider.closed is True
    assert _rows(database_url, conversation_id) == [("user", "Hello KAI")]


def test_reload_after_a_new_process_reads_postgres(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
) -> None:
    first = _client(monkeypatch, database_url)
    created = first.post("/api/v1/conversations", headers=_headers()).json()
    sent = first.post(
        "/api/v1/chat/stream",
        json={"message": "Hello KAI", "conversation_id": created["id"]},
        headers=_headers(),
    )
    assert sent.status_code == 200
    get_settings.cache_clear()
    second = TestClient(create_app())
    listed = second.get("/api/v1/conversations", headers=_headers())
    assert [item["id"] for item in listed.json()["conversations"]] == [created["id"]]
    loaded = second.get(f"/api/v1/conversations/{created['id']}", headers=_headers())
    assert loaded.json()["messages"][1]["content"] == "mock:mock-text:Hello KAI"


def test_chat_without_a_conversation_does_not_write_messages(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
) -> None:
    client = _client(monkeypatch, database_url)
    response = client.post("/api/v1/chat/stream", json={"message": "Hello KAI"}, headers=_headers())
    assert response.status_code == 200
    with psycopg.connect(database_url) as conn:
        count = conn.execute("SELECT count(*) FROM messages").fetchone()
    assert count is not None
    assert count[0] == 0


def test_missing_database_is_a_public_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAI_LOCAL_BEARER_TOKEN", TOKEN)
    monkeypatch.setenv("KAI_LOCAL_USER_ID", str(USER_A))
    monkeypatch.setenv("KAI_LOCAL_ORGANIZATION_ID", str(ORG_A))
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()
    missing = TestClient(create_app())
    response = missing.post("/api/v1/conversations", headers=_headers())
    assert response.status_code == 503
    assert response.json() == {"message": "A required dependency is unavailable."}

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://kai:super-secret-password@127.0.0.1:1/kai",
    )
    get_settings.cache_clear()
    down = TestClient(create_app())
    failed = down.post("/api/v1/conversations", headers=_headers())
    assert failed.status_code == 503
    assert "super-secret-password" not in failed.text
    assert "Traceback" not in failed.text


def test_persistence_does_not_import_the_model_provider() -> None:
    for path in (PERSISTENCE, CONVERSATIONS):
        text = path.read_text(encoding="utf-8")
        assert "MockModelProvider" not in text
        tree = ast.parse(text)
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert all(not module.startswith("kai_model_runtime") for module in modules)
    assert issubclass(ConversationStore, object)


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    *,
    organization_id: UUID = ORG_A,
    user_id: UUID = USER_A,
) -> None:
    monkeypatch.setenv("KAI_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("KAI_LOCAL_BEARER_TOKEN", TOKEN)
    monkeypatch.setenv("KAI_LOCAL_USER_ID", str(user_id))
    monkeypatch.setenv("KAI_LOCAL_ORGANIZATION_ID", str(organization_id))
    get_settings.cache_clear()


def _client(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    *,
    organization_id: UUID = ORG_A,
    user_id: UUID = USER_A,
) -> TestClient:
    _configure(
        monkeypatch,
        database_url,
        organization_id=organization_id,
        user_id=user_id,
    )
    return TestClient(create_app())


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def _rows(database_url: str, conversation_id: str | UUID) -> list[tuple[str, str]]:
    with psycopg.connect(database_url) as conn:
        cursor = conn.execute(
            """
            SELECT role::text, content
            FROM messages
            WHERE conversation_id = %s
            ORDER BY created_at ASC, id ASC
            """,
            (conversation_id,),
        )
        return [(str(role), str(content)) for role, content in cursor.fetchall()]


def _owner(database_url: str, conversation_id: str) -> UUID:
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "SELECT organization_id FROM conversations WHERE id = %s",
            (conversation_id,),
        ).fetchone()
    assert row is not None
    value = row[0]
    assert isinstance(value, UUID)
    return value


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
                parsed = json.loads(line.removeprefix("data: "))
                assert isinstance(parsed, dict)
                payload = {str(key): value for key, value in parsed.items()}
        frames.append((name, payload))
    return frames


async def _disconnect(app: object, conversation_id: str) -> tuple[int, bytes]:
    body = json.dumps({"message": "Hello KAI", "conversation_id": conversation_id}).encode()
    sent_body = False
    delta_seen = asyncio.Event()
    collected = bytearray()
    status = 0

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
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    await app(scope, receive, send)  # type: ignore[operator]
    return status, bytes(collected)


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


class _PausingProvider:
    provider_id = "mock"

    def __init__(self) -> None:
        self.closed = False

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            provider_id="mock",
            model_id="mock-text",
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
            yield "one"
            await asyncio.Event().wait()
            yield "two"
        finally:
            self.closed = True
