"""Load the shared product config so the API and web app agree on version."""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ProductConfig(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    product: str
    maker: str
    version: str
    phase: int
    api_version: str = Field(alias="apiVersion")
    ports: dict[str, int]


def find_repo_root(start: Path | None = None) -> Path:
    origin = start or Path(__file__).resolve()
    for candidate in [origin, *origin.parents]:
        config = candidate / "packages" / "config" / "kai.config.json"
        if config.is_file():
            return candidate
    raise FileNotFoundError("packages/config/kai.config.json not found")


@lru_cache
def get_product_config() -> ProductConfig:
    path = find_repo_root() / "packages" / "config" / "kai.config.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProductConfig.model_validate(payload)
