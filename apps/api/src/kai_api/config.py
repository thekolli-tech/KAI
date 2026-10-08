"""Environment-backed settings.

Secrets stay on the server. Health responses must not echo these fields.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from kai_api.product import find_repo_root
from kai_api.status import EnvironmentName


def _env_file() -> str | None:
    path = find_repo_root() / ".env"
    if path.is_file():
        return str(path)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=_env_file(),
        env_file_encoding="utf-8",
    )

    kai_env: EnvironmentName = EnvironmentName.DEVELOPMENT
    kai_api_host: str = "0.0.0.0"
    kai_api_port: int = 8000
    kai_web_origin: str = "http://localhost:3000"
    kai_log_level: str = "INFO"
    database_url: str = ""
    redis_url: str = ""
    qdrant_url: str = ""
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "kai-documents"
    minio_secure: bool = False
    kai_model_provider: str = "unconfigured"


@lru_cache
def get_settings() -> Settings:
    return Settings()
