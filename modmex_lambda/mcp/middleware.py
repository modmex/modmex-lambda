"""Composable middleware for MCP capabilities."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Protocol, TypeAlias, Union, Any

if TYPE_CHECKING:
    from modmex_lambda.event_handler.request import Request
    from modmex_lambda.mcp.server import MCPServer


JSONValue: TypeAlias = Union[
    None,
    bool,
    int,
    float,
    str,
    list["JSONValue"],
    dict[str, "JSONValue"],
]


@dataclass
class MCPContext:
    request: "Request | None"
    server: "MCPServer | None"
    capability: str
    name: str
    arguments: dict[str, JSONValue]
    state: dict[str, object] = field(default_factory=dict)


class MCPNextMiddleware(Protocol):
    def __call__(self, context: MCPContext) -> object: ...


class MCPMiddleware(Protocol):
    def __call__(self, context: MCPContext, next_middleware: MCPNextMiddleware) -> object: ...


def run_middleware(
    middlewares: list[MCPMiddleware],
    context: MCPContext,
    endpoint: Callable[[MCPContext], Any],
) -> Any:
    next_middleware: MCPNextMiddleware = endpoint
    for middleware in reversed(middlewares):
        current = next_middleware
        next_middleware = lambda ctx, middleware=middleware, current=current: middleware(ctx, current)
    result = next_middleware(context)
    if inspect.isawaitable(result):
        raise RuntimeError("MCP middleware is async; use run_middleware_async")
    return result


async def run_middleware_async(
    middlewares: list[MCPMiddleware],
    context: MCPContext,
    endpoint: Callable[[MCPContext], Any],
) -> Any:
    async def invoke(index: int, ctx: MCPContext) -> Any:
        if index == len(middlewares):
            result = endpoint(ctx)
        else:
            middleware = middlewares[index]
            result = middleware(ctx, lambda next_ctx: invoke(index + 1, next_ctx))
        return await result if inspect.isawaitable(result) else result
    return await invoke(0, context)
