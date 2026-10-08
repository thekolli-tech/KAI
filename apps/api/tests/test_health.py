from fastapi.testclient import TestClient

from kai_api.app import create_app
from kai_api.config import get_settings
from kai_api.product import get_product_config


def _client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(create_app())


def test_versioned_health_reports_phase_one_boundaries() -> None:
    response = _client().get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    product = get_product_config()
    assert body["status"] == "ok"
    assert body["service"] == "kai-api"
    assert body["version"] == product.version
    assert body["phase"] == product.phase
    assert body["checks"] == {
        "api": "ok",
        "engine": "interface_only",
        "model_runtime": "mock",
        "postgres": "not_configured",
        "redis": "not_configured",
        "qdrant": "not_configured",
        "minio": "not_configured",
    }
    assert response.headers["x-request-id"]


def test_probe_health_matches_versioned_health() -> None:
    client = _client()
    assert client.get("/health").json() == client.get("/api/v1/health").json()


def test_health_does_not_echo_secrets_or_provider_names(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://kai:super-secret-password@localhost/kai")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio-secret-value")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("KAI_MODEL_PROVIDER", "openai")
    body = _client().get("/api/v1/health").text
    assert "super-secret-password" not in body
    assert "minio-secret-value" not in body
    assert "openai" not in body
    assert '"model_runtime":"mock"' in body.replace(" ", "")
    assert "configured_unchecked" in body


def test_invalid_request_id_is_replaced() -> None:
    response = _client().get("/api/v1/health", headers={"x-request-id": "bad id\n"})
    assert response.status_code == 200
    assert "\n" not in response.headers["x-request-id"]
    assert response.headers["x-request-id"] != "bad id\n"


def test_health_route_stays_in_the_openapi_document() -> None:
    schema = _client().get("/api/v1/openapi.json").json()
    assert "/api/v1/health" in schema["paths"]
