import pytest

from kai_api.config import get_settings

_BLANK = {
    "DATABASE_URL": "",
    "REDIS_URL": "",
    "QDRANT_URL": "",
    "MINIO_ENDPOINT": "",
    "MINIO_ACCESS_KEY": "",
    "MINIO_SECRET_KEY": "",
    "KAI_MODEL_PROVIDER": "unconfigured",
    "KAI_ENV": "development",
    "KAI_LOCAL_BEARER_TOKEN": "",
    "KAI_LOCAL_USER_ID": "",
    "KAI_LOCAL_ORGANIZATION_ID": "",
}


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _BLANK.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
