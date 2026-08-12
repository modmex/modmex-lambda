"""MCP prompt registration and invocation."""

from __future__ import annotations

import inspect
from typing import Any, Callable, get_type_hints

from modmex_lambda.mcp.schema import input_schema
from modmex_lambda.mcp.tool import MCPTool
from modmex_lambda.mcp.middleware import MCPContext, MCPMiddleware


class MCPPrompt:
    def __init__(
        self,
        handler: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        middlewares: list[Any] | None = None,
    ) -> None:
        self.name = name or handler.__name__
        self.description = description or inspect.getdoc(handler) or ""
        self.operation = MCPTool(handler, middlewares=middlewares)

    def definition(self) -> dict[str, Any]:
        schema = input_schema(self.operation.handler)
        required = set(schema.get("required", []))
        properties = schema.get("properties", {})
        return {
            "name": self.name,
            "description": self.description,
            "arguments": [
                {"name": name, "description": str(properties[name].get("description", "")), "required": name in required}
                for name in properties
            ],
        }

    def get(self, arguments: dict[str, Any] | None = None, *, context: Any = None, server: Any = None, middlewares: list[MCPMiddleware] | None = None) -> dict[str, Any]:
        values = arguments or {}
        output = self.operation.invoke(values, request=context, middlewares=middlewares, middleware_context=MCPContext(request=context, server=server, capability="prompts", name=self.name, arguments=values))
        if not isinstance(output, list):
            output = [{"role": "user", "content": {"type": "text", "text": str(output)}}]
        return {"messages": output}

    async def aget(self, arguments: dict[str, Any] | None = None, *, context: Any = None, server: Any = None, middlewares: list[MCPMiddleware] | None = None) -> dict[str, Any]:
        values = arguments or {}
        output = await self.operation.ainvoke(values, request=context, middlewares=middlewares, middleware_context=MCPContext(request=context, server=server, capability="prompts", name=self.name, arguments=values))
        if not isinstance(output, list):
            output = [{"role": "user", "content": {"type": "text", "text": str(output)}}]
        return {"messages": output}
