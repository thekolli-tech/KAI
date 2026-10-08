"""Import boundaries for the engine package."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "kai_engine"
ORCHESTRATOR = SRC / "orchestrator.py"

BANNED_MODULES = (
    "openai",
    "anthropic",
    "google.generativeai",
    "ollama",
    "vllm",
    "fastapi",
    "starlette",
    "httpx",
    "aiohttp",
    "requests",
    "redis",
    "qdrant_client",
    "minio",
    "psycopg",
    "psycopg2",
    "asyncpg",
    "sqlalchemy",
    "boto3",
    "kai_model_runtime",
    "kai_tools",
    "kai_agents",
    "kai_memory",
    "kai_search",
    "kai_documents",
    "sse_starlette",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _banned(module: str) -> bool:
    return any(module == name or module.startswith(f"{name}.") for name in BANNED_MODULES)


def test_engine_package_imports_stay_inside_the_engine() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        for module in _imported_modules(path):
            if _banned(module):
                offenders.append(f"{path.name}: {module}")
    assert offenders == []


def test_orchestrator_calls_the_router_and_not_a_provider() -> None:
    source = ORCHESTRATOR.read_text(encoding="utf-8")
    assert "self._model_router.select" in source
    assert "self._model_router.execute" in source
    assert "self._model_router.stream" in source
    assert "MockModelProvider" not in source
    assert "GenerateRequest" not in source
    assert "text/event-stream" not in source


def test_engine_sources_do_not_mention_sse_or_the_mock_provider() -> None:
    banned = ("MockModelProvider", "text/event-stream", "sse_starlette", "EventSourceResponse")
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for name in banned:
            if name in text:
                offenders.append(f"{path.name}: {name}")
    assert offenders == []
