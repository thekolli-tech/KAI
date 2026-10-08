"""In-process registry for tools that actually implement execute()."""

from kai_tools.base import Tool, ToolSpec


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(name) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def list_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=tool.name,
                description=tool.description,
                input_schema=dict(tool.input_schema),
                permissions=tuple(tool.permissions),
                implemented=True,
            )
            for tool in self._tools.values()
        ]
