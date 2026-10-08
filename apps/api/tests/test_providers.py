from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ROOTS = (REPO_ROOT / "apps" / "api" / "src", REPO_ROOT / "services")
BANNED_IMPORTS = (
    "import openai",
    "from openai",
    "import anthropic",
    "from anthropic",
    "import google.generativeai",
    "from google.generativeai",
    "perplexity",
)


def test_python_sources_do_not_import_hosted_model_sdks() -> None:
    offenders: list[str] = []
    for root in ROOTS:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for banned in BANNED_IMPORTS:
                if banned in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {banned}")
    assert offenders == []
