"""Planned agents. None of these execute yet."""

from kai_agents.base import AgentSpec

PLANNED_AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        name="ResearchAgent",
        description="Gather sources through the search boundary.",
        capabilities=("research",),
        tools=("web_search", "web_fetch"),
        permissions=("network:read",),
        implemented=False,
    ),
    AgentSpec(
        name="CodingAgent",
        description="Read project files and draft code changes.",
        capabilities=("coding",),
        tools=("file_read", "file_search"),
        permissions=("file:read",),
        implemented=False,
    ),
    AgentSpec(
        name="DataAgent",
        description="Inspect tabular data and calculate.",
        capabilities=("data",),
        tools=("calculator", "file_read"),
        permissions=("calculation:execute", "file:read"),
        implemented=False,
    ),
    AgentSpec(
        name="DocumentAgent",
        description="Retrieve extracted document text.",
        capabilities=("documents",),
        tools=("file_read", "file_search"),
        permissions=("file:read",),
        implemented=False,
    ),
)
