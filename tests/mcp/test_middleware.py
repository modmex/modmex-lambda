from __future__ import annotations

import asyncio

from modmex_lambda.mcp import MCPContext, MCPServer
from tests.mcp.helpers import modern


class Recorder:
    def __init__(self, label: str, events: list[str]):
        self.label = label
        self.events = events

    def __call__(self, context: MCPContext, next_middleware):
        self.events.append(f"before:{self.label}")
        result = next_middleware(context)
        self.events.append(f"after:{self.label}")
        return result


def test_global_and_capability_middlewares_compose_in_order() -> None:
    events: list[str] = []
    server = MCPServer(name="loads")
    server.middleware(Recorder("global", events))

    @server.tool(middlewares=[Recorder("tool", events)])
    def lookup() -> str:
        events.append("handler")
        return "ok"

    response = server.handle(modern("tools/call", params={"name": "lookup"}))

    assert response is not None and response.error is None
    assert events == ["before:global", "before:tool", "handler", "after:tool", "after:global"]


def test_middleware_can_short_circuit() -> None:
    server = MCPServer(name="loads")

    def deny(context: MCPContext, next_middleware):
        return {"blocked": True}

    @server.tool(middlewares=[deny])
    def secret() -> str:
        raise AssertionError("handler must not run")

    response = server.handle(modern("tools/call", request_id=2, params={"name": "secret"}))
    assert response is not None and response.result["content"][0]["text"] == '{"blocked":true}'


def test_server_middleware_applies_when_registered_after_capability() -> None:
    events: list[str] = []
    server = MCPServer(name="loads")

    @server.tool()
    def lookup() -> str:
        events.append("handler")
        return "ok"

    def auth(context: MCPContext, next_middleware):
        events.append("auth")
        return next_middleware(context)

    server.middleware(auth)
    response = server.handle(modern("tools/call", params={"name": "lookup"}))

    assert response is not None and response.error is None
    assert events == ["auth", "handler"]


def test_async_middleware_chain_is_supported() -> None:
    server = MCPServer(name="loads")
    seen: list[str] = []

    async def middleware(context: MCPContext, next_middleware):
        seen.append("before")
        result = await next_middleware(context)
        seen.append("after")
        return result

    @server.tool(middlewares=[middleware])
    async def lookup() -> str:
        return "ok"

    async def run() -> None:
        response = await server.handle_async(modern("tools/call", request_id=3, params={"name": "lookup"}))
        assert response is not None and response.error is None

    asyncio.run(run())
    assert seen == ["before", "after"]


def test_http_context_is_available_to_mcp_context() -> None:
    server = MCPServer(name="loads")
    request = type("Request", (), {"context": {"user": {"sub": "u-1"}}})()

    @server.tool()
    def whoami(ctx: MCPContext) -> dict:
        return ctx.context["user"]

    response = server.handle(modern("tools/call", params={"name": "whoami"}), context=request)
    assert response is not None
    assert response.result["content"][0]["text"] == '{"sub":"u-1"}'
