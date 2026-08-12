from __future__ import annotations

import asyncio
from typing import Annotated

from modmex import BaseModel

from modmex_lambda import Depends
from modmex_lambda.mcp import MCPServer
from tests.mcp.helpers import modern


class SearchOptions(BaseModel):
    origin: str
    limit: int = 10


class Service:
    def search(self, origin: str) -> dict:
        return {"origin": origin}


def test_tools_list_uses_modmex_schema_and_hides_dependencies() -> None:
    server = MCPServer(name="loads")

    @server.tool()
    def search(
        options: SearchOptions,
        service: Annotated[Service, Depends()],
    ) -> dict:
        return service.search(options.origin)

    response = server.handle(modern("tools/list"))

    assert response is not None
    definition = response.result["tools"][0]
    assert definition["name"] == "search"
    assert definition["inputSchema"]["required"] == ["options"]
    assert definition["inputSchema"]["properties"]["options"]["properties"]["origin"]["type"] == "string"
    assert "service" not in definition["inputSchema"]["properties"]


def test_tools_call_resolves_annotated_dependencies_and_validates_arguments() -> None:
    server = MCPServer(name="loads")

    @server.tool()
    def search(
        origin: str,
        service: Annotated[Service, Depends()],
    ) -> dict:
        return service.search(origin)

    response = server.handle(modern("tools/call", request_id=2, params={"name": "search", "arguments": {"origin": "MEX"}}))

    assert response is not None
    assert response.result["isError"] is False
    assert '"origin":"MEX"' in response.result["content"][0]["text"]


def test_tools_call_reports_missing_and_unknown_arguments() -> None:
    server = MCPServer(name="loads")

    @server.tool()
    def search(origin: str) -> str:
        return origin

    missing = server.handle(modern("tools/call", request_id=3, params={"name": "search", "arguments": {}}))
    unknown = server.handle(modern("tools/call", request_id=4, params={"name": "search", "arguments": {"origin": "MEX", "x": 1}}))

    assert missing is not None and missing.error is not None
    assert unknown is not None and unknown.error is not None


def test_async_tool_uses_async_dispatch() -> None:
    server = MCPServer(name="loads")

    @server.tool()
    async def lookup(value: int) -> dict:
        return {"value": value}

    async def run() -> None:
        response = await server.handle_async(modern("tools/call", request_id=5, params={"name": "lookup", "arguments": {"value": 3}}))
        assert response is not None
        assert '"value":3' in response.result["content"][0]["text"]

    asyncio.run(run())


def test_tools_list_supports_opaque_pagination_cursor() -> None:
    server = MCPServer(name="loads")

    @server.tool(name="first")
    def first() -> str:
        return "first"

    @server.tool(name="second")
    def second() -> str:
        return "second"

    first_page = server.handle(modern("tools/list", params={"pageSize": 1}))
    second_page = server.handle(modern("tools/list", params={"cursor": first_page.result["nextCursor"], "pageSize": 1}))

    assert first_page.result["tools"][0]["name"] == "first"
    assert second_page.result["tools"][0]["name"] == "second"
    assert "nextCursor" not in second_page.result


def test_tools_call_preserves_structured_content() -> None:
    server = MCPServer(name="loads")

    @server.tool()
    def structured() -> dict:
        return {"content": [{"type": "text", "text": "created"}], "structuredContent": {"id": "A-1"}}

    response = server.handle(modern("tools/call", params={"name": "structured", "arguments": {}}))

    assert response.result["content"][0]["text"] == "created"
    assert response.result["structuredContent"] == {"id": "A-1"}
