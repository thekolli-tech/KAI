"""Typed failures for the local model runtime.

Messages are stable codes. Callers map them onto their own public errors.
"""


class ModelRuntimeError(Exception):
    """A runtime failure whose public code is ``args[0]``."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class UnknownProviderError(ModelRuntimeError):
    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id
        super().__init__("unknown_provider")


class UnknownModelError(ModelRuntimeError):
    def __init__(self, provider_id: str, model_id: str) -> None:
        self.provider_id = provider_id
        self.model_id = model_id
        super().__init__("unknown_model")


class RegistryConfigurationError(ModelRuntimeError):
    def __init__(self) -> None:
        super().__init__("registry_configuration")
