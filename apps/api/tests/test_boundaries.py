from uuid import uuid4

import pytest
from pydantic import ValidationError

from kai_agents import PLANNED_AGENTS
from kai_documents import PLANNED_DOCUMENT_KINDS
from kai_engine import EngineStage
from kai_engine.contracts import EngineRequest, Principal
from kai_model_runtime import ModelCapability
from kai_tools import FORBIDDEN_TOOL_NAMES, PLANNED_TOOLS, ToolRegistry


def test_engine_stages_cover_the_pipeline() -> None:
    assert [stage.value for stage in EngineStage] == [
        "intake",
        "intent",
        "context",
        "planning",
        "model_selection",
        "tool_selection",
        "agent_execution",
        "memory_retrieval",
        "tool_execution",
        "verification",
        "response",
    ]


def test_engine_request_rejects_an_empty_message() -> None:
    with pytest.raises(ValidationError):
        EngineRequest(
            request_id=uuid4(),
            principal=Principal(user_id=uuid4(), organization_id=uuid4()),
            message="",
        )


def test_planned_tools_are_not_implemented_and_exclude_shell() -> None:
    names = [tool.name for tool in PLANNED_TOOLS]
    assert names == ["calculator", "web_search", "web_fetch", "file_read", "file_search"]
    assert all(tool.implemented is False for tool in PLANNED_TOOLS)
    assert FORBIDDEN_TOOL_NAMES.isdisjoint(names)
    registry = ToolRegistry()
    assert registry.names() == ()

    class _Echo:
        name = "echo"
        description = "Registry test double."
        input_schema: dict[str, object] = {}
        permissions: tuple[str, ...] = ()

        async def execute(self, arguments: dict[str, object], context: object) -> object:
            return arguments, context

    registry.register(_Echo())
    assert registry.get("echo").name == "echo"
    assert registry.list_specs()[0].implemented is True


def test_planned_agents_are_not_implemented() -> None:
    names = [agent.name for agent in PLANNED_AGENTS]
    assert names == ["ResearchAgent", "CodingAgent", "DataAgent", "DocumentAgent"]
    assert all(agent.implemented is False for agent in PLANNED_AGENTS)


def test_document_kinds_and_model_capabilities_are_declared() -> None:
    assert {kind.value for kind in PLANNED_DOCUMENT_KINDS} == {
        "pdf",
        "docx",
        "xlsx",
        "pptx",
        "txt",
        "image",
        "source_code",
    }
    assert {item.value for item in ModelCapability} == {"text", "stream", "tools", "vision"}
