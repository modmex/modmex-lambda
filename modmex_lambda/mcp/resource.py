"""MCP resource URI templates and invocation."""

from __future__ import annotations

import re
from typing import Any, Callable

from modmex_lambda.mcp.tool import MCPTool
from modmex_lambda.mcp.middleware import MCPContext, MCPMiddleware


class MCPResource:
    def __init__(
        self,
        uri_template: str,
        handler: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        mime_type: str = "application/json",
        middlewares: list[Any] | None = None,
    ) -> None:
        if not uri_template:
            raise ValueError("MCP resource URI template cannot be empty")
        self.uri_template = uri_template
        self.name = name or uri_template
        self.description = description or ""
        self.mime_type = mime_type
        self.operation = MCPTool(handler, middlewares=middlewares)
        self._names = tuple(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", uri_template))
        pattern = re.escape(uri_template)
        for parameter in self._names:
            pattern = pattern.replace("\\{" + parameter + "\\}", rf"(?P<{parameter}>[^/]+)")
        self._pattern = re.compile(rf"^{pattern}$")

    def match(self, uri: str) -> dict[str, str] | None:
        matched = self._pattern.match(uri)
        return matched.groupdict() if matched else None

    def definition(self) -> dict[str, Any]:
        return {
            "uri": self.uri_template,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }

    def template_definition(self) -> dict[str, Any]:
        definition = self.definition()
        definition.pop("uri", None)
        definition["uriTemplate"] = self.uri_template
        return definition

    def read(self, uri: str, *, context: Any = None, server: Any = None, middlewares: list[MCPMiddleware] | None = None) -> dict[str, Any]:
        arguments = self.match(uri)
        if arguments is None:
            raise ValueError(f"Resource URI does not match: {uri}")
        output = self.operation.invoke(arguments, request=context, middlewares=middlewares, middleware_context=MCPContext(request=context, server=server, capability="resources", name=self.name, arguments=arguments))
        if isinstance(output, bytes):
            import base64
            return {"uri": uri, "mimeType": self.mime_type, "blob": base64.b64encode(output).decode()}
        if isinstance(output, str):
            return {"uri": uri, "mimeType": self.mime_type, "text": output}
        return {"uri": uri, "mimeType": self.mime_type, "text": _json_text(output)}

    async def aread(self, uri: str, *, context: Any = None, server: Any = None, middlewares: list[MCPMiddleware] | None = None) -> dict[str, Any]:
        arguments = self.match(uri)
        if arguments is None:
            raise ValueError(f"Resource URI does not match: {uri}")
        output = await self.operation.ainvoke(arguments, request=context, middlewares=middlewares, middleware_context=MCPContext(request=context, server=server, capability="resources", name=self.name, arguments=arguments))
        if isinstance(output, bytes):
            import base64
            return {"uri": uri, "mimeType": self.mime_type, "blob": base64.b64encode(output).decode()}
        if isinstance(output, str):
            return {"uri": uri, "mimeType": self.mime_type, "text": output}
        return {"uri": uri, "mimeType": self.mime_type, "text": _json_text(output)}


def _json_text(value: Any) -> str:
    import json
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return json.dumps(value, default=str, separators=(",", ":"))
