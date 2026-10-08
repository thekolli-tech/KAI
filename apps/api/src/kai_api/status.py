"""Public status values shared by health responses."""

from enum import StrEnum


class EnvironmentName(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class CheckState(StrEnum):
    OK = "ok"
    INTERFACE_ONLY = "interface_only"
    NOT_CONFIGURED = "not_configured"
    CONFIGURED_UNCHECKED = "configured_unchecked"
