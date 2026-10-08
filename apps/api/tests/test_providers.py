import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ROOTS = (REPO_ROOT / "apps" / "api" / "src", REPO_ROOT / "services")
BANNED_MODULES = (
    "openai",
    "anthropic",
    "google.generativeai",
    "ollama",
    "vllm",
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


def test_python_sources_do_not_import_hosted_model_sdks() -> None:
    offenders: list[str] = []
    for root in ROOTS:
        for path in root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            for module in _imported_modules(path):
                if any(module == name or module.startswith(f"{name}.") for name in BANNED_MODULES):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {module}")
    assert offenders == []
