"""Planned tools.

These records describe the first tool set. They are not registered and
their execute paths do not exist. implemented is false on purpose.
"""

from kai_tools.base import ToolSpec

_OBJECT = "object"

PLANNED_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="calculator",
        description="Evaluate a single arithmetic expression.",
        input_schema={
            "type": _OBJECT,
            "additionalProperties": False,
            "required": ["expression"],
            "properties": {"expression": {"type": "string", "maxLength": 200}},
        },
        permissions=("calculation:execute",),
        implemented=False,
    ),
    ToolSpec(
        name="web_search",
        description="Search the configured search provider.",
        input_schema={
            "type": _OBJECT,
            "additionalProperties": False,
            "required": ["query"],
            "properties": {"query": {"type": "string", "maxLength": 500}},
        },
        permissions=("network:read",),
        implemented=False,
    ),
    ToolSpec(
        name="web_fetch",
        description="Fetch a public URL through the search boundary.",
        input_schema={
            "type": _OBJECT,
            "additionalProperties": False,
            "required": ["url"],
            "properties": {"url": {"type": "string", "maxLength": 2000}},
        },
        permissions=("network:read",),
        implemented=False,
    ),
    ToolSpec(
        name="file_read",
        description="Read one organization-owned file by id.",
        input_schema={
            "type": _OBJECT,
            "additionalProperties": False,
            "required": ["file_id"],
            "properties": {"file_id": {"type": "string"}},
        },
        permissions=("file:read",),
        implemented=False,
    ),
    ToolSpec(
        name="file_search",
        description="Search file names and extracted text inside one organization.",
        input_schema={
            "type": _OBJECT,
            "additionalProperties": False,
            "required": ["query"],
            "properties": {"query": {"type": "string", "maxLength": 500}},
        },
        permissions=("file:read",),
        implemented=False,
    ),
)

FORBIDDEN_TOOL_NAMES = frozenset(
    {"shell", "bash", "sh", "exec", "system", "subprocess", "code_exec"}
)
