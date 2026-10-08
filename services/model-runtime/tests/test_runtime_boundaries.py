"""Import boundaries for the model runtime package."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "kai_model_runtime"
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
    "urllib",
    "socket",
    "kai_engine",
    "kai_api",
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


def test_model_runtime_does_not_import_the_engine_or_provider_sdks() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        for module in _imported_modules(path):
            if any(module == name or module.startswith(f"{name}.") for name in BANNED_MODULES):
                offenders.append(f"{path.name}: {module}")
    assert offenders == []
