"""RegisteredModelRouter tests. Providers are in-memory doubles."""

import asyncio
from uuid import uuid4

import pytest

from kai_api.model_router import RegisteredModelRouter
from kai_engine.context import CancellationToken, ExecutionContext
from kai_engine.contracts import EngineRequest, ModelChoice, Principal, TaskPlan
from kai_engine.errors import ExecutionFailureError, ProviderUnavailableError
from kai_model_runtime import (
    GenerateRequest,
    ModelCapabilities,
    ModelCapability,
    ModelOutput,
    ProviderRegistry,
)


class _Provider:
    def __init__(self, provider_id: str = "local", model_id: str = "text") -> None:
        self.provider_id = provider_id
        self.model_id = model_id
        self.healthy = True
        self.fail_health = False
        self.fail_generate = False
        self.generate_calls = 0
        self.output_provider_id = provider_id
        self.output_model_id = model_id

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            provider_id=self.provider_id,
            model_id=self.model_id,
            capabilities=(ModelCapability.TEXT, ModelCapability.STREAM),
            max_context_tokens=32,
        )

    async def health_check(self) -> bool:
        if self.fail_health:
            raise RuntimeError("health dependency down")
        return self.healthy

    async def generate(self, request: GenerateRequest) -> ModelOutput:
        self.generate_calls += 1
        if self.fail_generate:
            raise RuntimeError("generation failed")
        return ModelOutput(
            provider_id=self.output_provider_id,
            model_id=self.output_model_id,
            text=f"out:{request.prompt}",
            finish_reason="stop",
        )

    async def stream(self, request: GenerateRequest):
        yield request.prompt


def _request() -> EngineRequest:
    return EngineRequest(
        request_id=uuid4(),
        principal=Principal(user_id=uuid4(), organization_id=uuid4()),
        message="route this",
    )


def _context(request: EngineRequest) -> ExecutionContext:
    return ExecutionContext(
        request_id=request.request_id,
        run_id=uuid4(),
        user_id=request.principal.user_id,
        organization_id=request.principal.organization_id,
        conversation_id=None,
        user_input=request.message,
        cancellation=CancellationToken(),
    )


def _router(provider: _Provider) -> RegisteredModelRouter:
    return RegisteredModelRouter(
        registry=ProviderRegistry({provider.provider_id: provider}),
        provider_id=provider.provider_id,
        model_id=provider.model_id,
    )


def test_select_and_execute_use_the_registered_provider() -> None:
    provider = _Provider()
    router = _router(provider)
    request = _request()
    plan = TaskPlan(steps=[], required_capabilities=[])
    choice = asyncio.run(router.select(request, plan, context=_context(request)))
    text = asyncio.run(router.execute(request, choice))
    assert choice == ModelChoice(provider_id="local", model_id="text")
    assert text == "out:route this"
    assert provider.generate_calls == 1


def test_unknown_provider_is_provider_unavailable() -> None:
    router = _router(_Provider())
    selection = ModelChoice(provider_id="missing", model_id="text")
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(router.execute(_request(), selection))


def test_unknown_model_is_provider_unavailable() -> None:
    router = _router(_Provider())
    selection = ModelChoice(provider_id="local", model_id="missing")
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(router.execute(_request(), selection))


def test_unhealthy_provider_does_not_generate() -> None:
    provider = _Provider()
    provider.healthy = False
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(router_execute(provider))
    assert provider.generate_calls == 0


def test_health_check_exception_is_provider_unavailable() -> None:
    provider = _Provider()
    provider.fail_health = True
    with pytest.raises(ProviderUnavailableError) as caught:
        asyncio.run(router_execute(provider))
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert provider.generate_calls == 0


def test_generate_exception_is_execution_failure() -> None:
    provider = _Provider()
    provider.fail_generate = True
    with pytest.raises(ExecutionFailureError) as caught:
        asyncio.run(router_execute(provider))
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_mismatched_output_identity_is_execution_failure() -> None:
    provider = _Provider()
    provider.output_model_id = "elsewhere"
    with pytest.raises(ExecutionFailureError):
        asyncio.run(router_execute(provider))


def router_execute(provider: _Provider) -> str:
    request = _request()
    router = _router(provider)
    choice = ModelChoice(provider_id=provider.provider_id, model_id=provider.model_id)
    return asyncio.run(router.execute(request, choice))
