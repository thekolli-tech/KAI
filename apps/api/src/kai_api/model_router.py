"""ModelRouter implementation. Providers are injected through a registry."""

from kai_engine.context import ExecutionContext
from kai_engine.contracts import EngineRequest, ModelChoice, TaskPlan
from kai_engine.errors import ExecutionFailureError, ProviderUnavailableError
from kai_model_runtime import GenerateRequest, ModelProvider
from kai_model_runtime.errors import UnknownModelError, UnknownProviderError
from kai_model_runtime.registry import ProviderRegistry


class RegisteredModelRouter:
    """Select a registered model and execute it through ``ModelProvider``."""

    def __init__(self, *, registry: ProviderRegistry, provider_id: str, model_id: str) -> None:
        self._registry = registry
        self._provider_id = provider_id
        self._model_id = model_id

    async def select(
        self,
        request: EngineRequest,
        plan: TaskPlan,
        *,
        context: ExecutionContext,
    ) -> ModelChoice:
        del request, plan, context
        self._resolve(self._provider_id, self._model_id)
        return ModelChoice(provider_id=self._provider_id, model_id=self._model_id)

    async def execute(self, request: EngineRequest, selection: ModelChoice) -> str:
        provider = self._resolve(selection.provider_id, selection.model_id)
        try:
            healthy = await provider.health_check()
        except Exception as exc:
            raise ProviderUnavailableError from exc
        if not healthy:
            raise ProviderUnavailableError
        try:
            output = await provider.generate(
                GenerateRequest(model_id=selection.model_id, prompt=request.message)
            )
        except Exception as exc:
            raise ExecutionFailureError from exc
        if output.provider_id != selection.provider_id or output.model_id != selection.model_id:
            raise ExecutionFailureError
        return output.text

    def _resolve(self, provider_id: str, model_id: str) -> ModelProvider:
        try:
            return self._registry.resolve(provider_id, model_id)
        except UnknownProviderError as exc:
            raise ProviderUnavailableError from exc
        except UnknownModelError as exc:
            raise ProviderUnavailableError from exc
