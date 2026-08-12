"""Transport-neutral MCP server dispatcher."""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Callable

from modmex_lambda.mcp.protocol import (
    JSONRPCErrorCode,
    JSONRPCRequest,
    JSONRPCResponse,
)
from modmex_lambda.mcp.registry import MCPToolRegistry
from modmex_lambda.mcp.registry import MCPPromptRegistry, MCPResourceRegistry
from modmex_lambda.mcp.prompt import MCPPrompt
from modmex_lambda.mcp.resource import MCPResource
from modmex_lambda.mcp.tool import MCPTool
from modmex_lambda.mcp.middleware import MCPContext, MCPMiddleware

from modmex_lambda.mcp.protocol import MCP_PROTOCOL_VERSION

SUPPORTED_PROTOCOL_VERSIONS = frozenset({MCP_PROTOCOL_VERSION})
logger = logging.getLogger(__name__)


class MCPError(Exception):
    """Controlled error whose message is safe to return to an MCP client."""


class MCPServer:
    """Dispatch the MCP lifecycle methods that do not require a transport.

    Keeping this object transport-neutral makes the protocol behavior testable
    without constructing an API Gateway event.
    """

    def __init__(
        self,
        *,
        name: str,
        version: str = "0.1.0",
        protocol_version: str = MCP_PROTOCOL_VERSION,
    ) -> None:
        if not name:
            raise ValueError("MCP server name cannot be empty")
        self.name = name
        self.version = version
        self.protocol_version = protocol_version
        self._methods: dict[str, Callable[..., Any]] = {
            "server/discover": self._discover,
            "tools/list": self._tools_list,
            "tools/call": self._tools_call,
            "resources/list": self._resources_list,
            "resources/templates/list": self._resources_templates_list,
            "resources/read": self._resources_read,
            "prompts/list": self._prompts_list,
            "prompts/get": self._prompts_get,
        }
        self.tools = MCPToolRegistry()
        self.resources = MCPResourceRegistry()
        self.prompts = MCPPromptRegistry()
        self.middlewares: list[MCPMiddleware] = []

    def middleware(self, middleware: MCPMiddleware) -> MCPMiddleware:
        self.middlewares.append(middleware)
        return middleware

    def tool(
        self,
        name: str | None = None,
        description: str | None = None,
        middlewares: list[MCPMiddleware] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.tools.add(MCPTool(handler, name=name, description=description, middlewares=middlewares))
            return handler

        return decorator

    def add_tool(
        self,
        handler: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        middlewares: list[MCPMiddleware] | None = None,
    ) -> Callable[..., Any]:
        self.tools.add(MCPTool(handler, name=name, description=description, middlewares=middlewares))
        return handler

    def resource(
        self,
        uri_template: str,
        *,
        name: str | None = None,
        description: str | None = None,
        mime_type: str = "application/json",
        middlewares: list[MCPMiddleware] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.resources.add(MCPResource(uri_template, handler, name=name, description=description, mime_type=mime_type, middlewares=middlewares))
            return handler
        return decorator

    def prompt(
        self,
        name: str | None = None,
        description: str | None = None,
        middlewares: list[MCPMiddleware] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.prompts.add(MCPPrompt(handler, name=name, description=description, middlewares=middlewares))
            return handler
        return decorator

    @property
    def methods(self) -> tuple[str, ...]:
        """Methods currently exposed by this server."""
        return tuple(self._methods)

    def handle(
        self,
        request: JSONRPCRequest | dict[str, Any],
        *,
        context: Any = None,
    ) -> JSONRPCResponse | None:
        """Handle one already-parsed JSON-RPC request synchronously."""
        request_id = request.get("id") if isinstance(request, dict) else request.id
        try:
            parsed = self._coerce_request(request)
        except MCPError as exc:
            response = JSONRPCResponse.failure(parsed.id, JSONRPCErrorCode.INTERNAL_ERROR, str(exc))
            return None if self._is_notification(request) else response
        except ValueError as exc:
            return JSONRPCResponse.failure(
                request_id,
                JSONRPCErrorCode.INVALID_REQUEST,
                str(exc),
            )
        try:
            self._validate_metadata(parsed)
        except MCPError as exc:
            response = JSONRPCResponse.failure(parsed.id, JSONRPCErrorCode.INTERNAL_ERROR, str(exc))
            return None if self._is_notification(request) else response
        except ValueError as exc:
            return JSONRPCResponse.failure(parsed.id, JSONRPCErrorCode.UNSUPPORTED_PROTOCOL_VERSION, str(exc), {
                "supported": sorted(SUPPORTED_PROTOCOL_VERSIONS),
                "requested": parsed.metadata.get("io.modelcontextprotocol/protocolVersion"),
            })
        method = self._methods.get(parsed.method)
        if method is None:
            return JSONRPCResponse.failure(
                parsed.id,
                JSONRPCErrorCode.METHOD_NOT_FOUND,
                f"Method not found: {parsed.method}",
            )

        try:
            result = method(parsed.params or {}, context=context)
            if inspect.isawaitable(result):
                raise RuntimeError(
                    f"MCP method {parsed.method!r} is asynchronous; use handle_async"
                )
            return None if self._is_notification(request) else JSONRPCResponse.success(parsed.id, result)
        except ValueError as exc:
            response = JSONRPCResponse.failure(
                parsed.id,
                JSONRPCErrorCode.INVALID_PARAMS,
                str(exc),
            )
            return None if self._is_notification(request) else response
        except Exception as exc:
            logger.exception("Unhandled MCP error in %s", parsed.method)
            response = JSONRPCResponse.failure(
                parsed.id,
                JSONRPCErrorCode.INTERNAL_ERROR,
                "Internal server error",
            )
            return None if self._is_notification(request) else response

    async def handle_async(
        self,
        request: JSONRPCRequest | dict[str, Any],
        *,
        context: Any = None,
    ) -> JSONRPCResponse | None:
        """Handle one already-parsed JSON-RPC request with async support."""
        request_id = request.get("id") if isinstance(request, dict) else request.id
        try:
            parsed = self._coerce_request(request)
        except ValueError as exc:
            return JSONRPCResponse.failure(
                request_id,
                JSONRPCErrorCode.INVALID_REQUEST,
                str(exc),
            )
        try:
            self._validate_metadata(parsed)
        except ValueError as exc:
            return JSONRPCResponse.failure(parsed.id, JSONRPCErrorCode.UNSUPPORTED_PROTOCOL_VERSION, str(exc), {
                "supported": sorted(SUPPORTED_PROTOCOL_VERSIONS),
                "requested": parsed.metadata.get("io.modelcontextprotocol/protocolVersion"),
            })
        method = self._methods.get(parsed.method)
        if method is None:
            return JSONRPCResponse.failure(
                parsed.id,
                JSONRPCErrorCode.METHOD_NOT_FOUND,
                f"Method not found: {parsed.method}",
            )

        try:
            if parsed.method == "tools/call":
                result = await self._tools_call_async(parsed.params or {}, context=context)
            elif parsed.method == "resources/read":
                result = await self._resources_read_async(parsed.params or {}, context=context)
            elif parsed.method == "prompts/get":
                result = await self._prompts_get_async(parsed.params or {}, context=context)
            else:
                result = method(parsed.params or {}, context=context)
            if inspect.isawaitable(result):
                result = await result
            return None if self._is_notification(request) else JSONRPCResponse.success(parsed.id, result)
        except ValueError as exc:
            response = JSONRPCResponse.failure(
                parsed.id,
                JSONRPCErrorCode.INVALID_PARAMS,
                str(exc),
            )
            return None if self._is_notification(request) else response
        except Exception as exc:
            logger.exception("Unhandled async MCP error in %s", parsed.method)
            response = JSONRPCResponse.failure(
                parsed.id,
                JSONRPCErrorCode.INTERNAL_ERROR,
                "Internal server error",
            )
            return None if self._is_notification(request) else response

    def handle_batch(
        self,
        requests: list[JSONRPCRequest | dict[str, Any]],
        *,
        context: Any = None,
    ) -> list[JSONRPCResponse]:
        """Handle a JSON-RPC batch, omitting notification responses."""
        responses = [self.handle(request, context=context) for request in requests]
        return [response for response in responses if response is not None]

    async def handle_batch_async(
        self,
        requests: list[JSONRPCRequest | dict[str, Any]],
        *,
        context: Any = None,
    ) -> list[JSONRPCResponse]:
        responses = [
            await self.handle_async(request, context=context)
            for request in requests
        ]
        return [response for response in responses if response is not None]

    def _coerce_request(
        self,
        request: JSONRPCRequest | dict[str, Any],
    ) -> JSONRPCRequest:
        if isinstance(request, JSONRPCRequest):
            return request
        try:
            return JSONRPCRequest(**request)
        except Exception as exc:
            raise ValueError(f"Invalid JSON-RPC request: {exc}") from exc

    @staticmethod
    def _is_notification(request: JSONRPCRequest | dict[str, Any]) -> bool:
        return isinstance(request, dict) and "id" not in request

    def _validate_metadata(self, request: JSONRPCRequest) -> None:
        version = request.metadata.get("io.modelcontextprotocol/protocolVersion")
        if version not in SUPPORTED_PROTOCOL_VERSIONS:
            raise ValueError(f"Unsupported protocol version: {version}")

    def _discover(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        return {
            "resultType": "complete",
            "supportedVersions": sorted(SUPPORTED_PROTOCOL_VERSIONS),
            "capabilities": {
                **({"tools": {}} if self.tools.definitions() else {}),
                **({"resources": {}} if (self.resources.definitions() or self.resources.templates()) else {}),
                **({"prompts": {}} if self.prompts.definitions() else {}),
            },
            "_meta": {
                "io.modelcontextprotocol/serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            },
            "ttlMs": 3600000,
            "cacheScope": "public",
        }

    def _tools_list(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        tools, next_cursor = self.tools.page(params.get("cursor"), limit=params.get("pageSize", 50))
        return _list_result("tools", tools, next_cursor)

    def _tools_call(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            raise ValueError("tools/call requires a string 'name'")
        tool = self.tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("tools/call 'arguments' must be an object")
        output = tool.invoke(arguments, request=context, middlewares=self.middlewares, middleware_context=MCPContext(request=context, server=self, capability="tools", name=name, arguments=arguments))
        return _tool_result(output)

    def _resources_list(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        resources, next_cursor = self.resources.page(params.get("cursor"), limit=params.get("pageSize", 50))
        return _list_result("resources", resources, next_cursor)

    def _resources_templates_list(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        templates, next_cursor = self.resources.page(params.get("cursor"), templates=True, limit=params.get("pageSize", 50))
        return _list_result("resourceTemplates", templates, next_cursor)

    def _resources_read(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        uri = params.get("uri")
        if not isinstance(uri, str):
            raise ValueError("resources/read requires a string 'uri'")
        matched = self.resources.match(uri)
        if matched is None:
            raise ValueError(f"Unknown resource URI: {uri}")
        resource, _ = matched
        return {"resultType": "complete", "contents": [resource.read(uri, context=context, server=self, middlewares=self.middlewares)], "ttlMs": 60000, "cacheScope": "private"}

    def _prompts_list(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        prompts, next_cursor = self.prompts.page(params.get("cursor"), limit=params.get("pageSize", 50))
        return _list_result("prompts", prompts, next_cursor)

    def _prompts_get(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            raise ValueError("prompts/get requires a string 'name'")
        prompt = self.prompts.get(name)
        if prompt is None:
            raise ValueError(f"Unknown prompt: {name}")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("prompts/get 'arguments' must be an object")
        return {"resultType": "complete", **prompt.get(arguments, context=context, server=self, middlewares=self.middlewares), "ttlMs": 300000, "cacheScope": "private"}

    async def _tools_call_async(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            raise ValueError("tools/call requires a string 'name'")
        tool = self.tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("tools/call 'arguments' must be an object")
        output = await tool.ainvoke(arguments, request=context, middlewares=self.middlewares, middleware_context=MCPContext(request=context, server=self, capability="tools", name=name, arguments=arguments))
        return _tool_result(output)

    async def _resources_read_async(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        uri = params.get("uri")
        if not isinstance(uri, str):
            raise ValueError("resources/read requires a string 'uri'")
        matched = self.resources.match(uri)
        if matched is None:
            raise ValueError(f"Unknown resource URI: {uri}")
        resource, _ = matched
        return {"resultType": "complete", "contents": [await resource.aread(uri, context=context, server=self, middlewares=self.middlewares)], "ttlMs": 60000, "cacheScope": "private"}

    async def _prompts_get_async(self, params: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            raise ValueError("prompts/get requires a string 'name'")
        prompt = self.prompts.get(name)
        if prompt is None:
            raise ValueError(f"Unknown prompt: {name}")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("prompts/get 'arguments' must be an object")
        return {"resultType": "complete", **await prompt.aget(arguments, context=context, server=self, middlewares=self.middlewares), "ttlMs": 300000, "cacheScope": "private"}


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return json.dumps(value, default=str, separators=(",", ":"))


def _list_result(key: str, values: list[dict[str, Any]], next_cursor: str | None) -> dict[str, Any]:
    result = {"resultType": "complete", key: values, "ttlMs": 300000, "cacheScope": "public"}
    if next_cursor is not None:
        result["nextCursor"] = next_cursor
    return result


def _tool_result(output: Any) -> dict[str, Any]:
    structured = getattr(output, "structured_content", None)
    content = getattr(output, "content", None)
    is_error = getattr(output, "is_error", False)
    if isinstance(output, dict) and ("structuredContent" in output or "content" in output):
        structured = output.get("structuredContent")
        content = output.get("content")
        is_error = output.get("isError", False)
    if content is None:
        content = [{"type": "text", "text": _json_text(output)}]
    elif isinstance(content, str):
        content = [{"type": "text", "text": content}]
    result = {"resultType": "complete", "content": content, "isError": bool(is_error)}
    if structured is not None:
        result["structuredContent"] = structured
    return result
