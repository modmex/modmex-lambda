"""Capability registries used by the MCP server."""

from __future__ import annotations

from typing import Any

from modmex_lambda.mcp.tool import MCPTool
from modmex_lambda.mcp.prompt import MCPPrompt
from modmex_lambda.mcp.resource import MCPResource


class MCPToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, MCPTool] = {}

    def add(self, tool: MCPTool) -> MCPTool:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate MCP tool: {tool.name}")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> MCPTool | None:
        return self._tools.get(name)

    def definitions(self) -> list[dict[str, Any]]:
        return [tool.definition() for tool in self._tools.values()]

    def page(self, cursor: str | None = None, *, limit: int = 50) -> tuple[list[dict[str, Any]], str | None]:
        return _page(self.definitions(), cursor, limit)


class MCPResourceRegistry:
    def __init__(self) -> None:
        self._resources: list[MCPResource] = []

    def add(self, resource: MCPResource) -> MCPResource:
        if any(item.uri_template == resource.uri_template for item in self._resources):
            raise ValueError(f"Duplicate MCP resource: {resource.uri_template}")
        self._resources.append(resource)
        return resource

    def match(self, uri: str) -> tuple[MCPResource, dict[str, str]] | None:
        for resource in self._resources:
            arguments = resource.match(uri)
            if arguments is not None:
                return resource, arguments
        return None

    def definitions(self) -> list[dict[str, Any]]:
        return [resource.definition() for resource in self._resources if "{" not in resource.uri_template]

    def templates(self) -> list[dict[str, Any]]:
        return [resource.template_definition() for resource in self._resources if "{" in resource.uri_template]

    def page(self, cursor: str | None = None, *, templates: bool = False, limit: int = 50) -> tuple[list[dict[str, Any]], str | None]:
        values = self.templates() if templates else self.definitions()
        return _page(values, cursor, limit)


class MCPPromptRegistry:
    def __init__(self) -> None:
        self._prompts: dict[str, MCPPrompt] = {}

    def add(self, prompt: MCPPrompt) -> MCPPrompt:
        if prompt.name in self._prompts:
            raise ValueError(f"Duplicate MCP prompt: {prompt.name}")
        self._prompts[prompt.name] = prompt
        return prompt

    def get(self, name: str) -> MCPPrompt | None:
        return self._prompts.get(name)

    def definitions(self) -> list[dict[str, Any]]:
        return [prompt.definition() for prompt in self._prompts.values()]

    def page(self, cursor: str | None = None, *, limit: int = 50) -> tuple[list[dict[str, Any]], str | None]:
        return _page(self.definitions(), cursor, limit)


def _page(values: list[dict[str, Any]], cursor: str | None, limit: int) -> tuple[list[dict[str, Any]], str | None]:
    if limit <= 0:
        raise ValueError("page size must be positive")
    try:
        start = int(cursor) if cursor is not None else 0
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid pagination cursor") from exc
    if start < 0 or start > len(values):
        raise ValueError("invalid pagination cursor")
    end = min(start + min(limit, 100), len(values))
    return values[start:end], str(end) if end < len(values) else None
