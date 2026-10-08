"""MockModelProvider contract tests. No network and no external services."""

import ast
import asyncio
from pathlib import Path

import pytest

from kai_model_runtime import GenerateRequest, MockModelProvider, ModelCapability
from kai_model_runtime.errors import UnknownModelError

PROMPT = "phase three"
SYSTEM = "local"


def _provider(**kwargs: object) -> MockModelProvider:
    values: dict[str, object] = {"provider_id": "mock", "model_id": "mock-text"}
    values.update(kwargs)
    return MockModelProvider(**values)  # type: ignore[arg-type]


def _request(model_id: str = "mock-text", system: str | None = None) -> GenerateRequest:
    return GenerateRequest(model_id=model_id, prompt=PROMPT, system=system)


def test_generate_is_deterministic_and_names_the_provider() -> None:
    provider = _provider()
    request = _request()
    first = asyncio.run(provider.generate(request))
    second = asyncio.run(provider.generate(request))
    assert first == second
    assert first.provider_id == "mock"
    assert first.model_id == "mock-text"
    assert first.finish_reason == "stop"
    assert first.text == "mock:mock-text:phase three"


def test_configured_response_replaces_the_default_rendering() -> None:
    provider = _provider(responses={PROMPT: "fixture-text"})
    output = asyncio.run(provider.generate(_request(system=SYSTEM)))
    assert output.text == "fixture-text"


def test_system_text_is_part_of_the_default_rendering() -> None:
    output = asyncio.run(_provider().generate(_request(system=SYSTEM)))
    assert output.text == "mock:mock-text:local:phase three"


def test_unknown_model_id_is_rejected() -> None:
    with pytest.raises(UnknownModelError) as caught:
        asyncio.run(_provider().generate(_request(model_id="other")))
    assert caught.value.model_id == "other"
    assert caught.value.code == "unknown_model"


def test_stream_chunks_are_ordered_and_reconstruct_the_text() -> None:
    provider = _provider(chunk_size=4, responses={PROMPT: "abcdefghij"})

    async def collect() -> list[str]:
        return [chunk async for chunk in provider.stream(_request())]

    chunks = asyncio.run(collect())
    generated = asyncio.run(provider.generate(_request()))
    assert chunks == ["abcd", "efgh", "ij"]
    assert "".join(chunks) == generated.text


def test_empty_configured_text_streams_nothing() -> None:
    provider = _provider(responses={PROMPT: ""})

    async def collect() -> list[str]:
        return [chunk async for chunk in provider.stream(_request())]

    assert asyncio.run(collect()) == []
    assert asyncio.run(provider.generate(_request())).text == ""


def test_capabilities_report_text_and_streaming_only() -> None:
    capabilities = _provider(max_context_tokens=128).get_capabilities()
    assert capabilities.provider_id == "mock"
    assert capabilities.model_id == "mock-text"
    assert capabilities.max_context_tokens == 128
    assert capabilities.capabilities == (ModelCapability.TEXT, ModelCapability.STREAM)
    assert ModelCapability.TOOLS not in capabilities.capabilities
    assert ModelCapability.VISION not in capabilities.capabilities


def test_health_check_is_deterministic() -> None:
    assert asyncio.run(_provider().health_check()) is True
    assert asyncio.run(_provider().health_check()) is True
    assert asyncio.run(_provider(healthy=False).health_check()) is False


def test_mock_source_has_no_sleep_or_network_client() -> None:
    source = Path(__file__).resolve().parents[1] / "src" / "kai_model_runtime" / "mock.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "sleep" not in names
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert modules.isdisjoint({"httpx", "urllib", "socket", "openai", "requests"})
