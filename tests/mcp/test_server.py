from __future__ import annotations

import asyncio

from modmex_lambda.mcp import JSONRPCErrorCode, MCPServer
from tests.mcp.helpers import modern


def test_discover_returns_modern_metadata_and_capabilities() -> None:
    response = MCPServer(name="loads", version="1.2.3").handle(modern("server/discover"))
    assert response.error is None
    assert response.result["supportedVersions"] == ["2026-07-28"]
    assert response.result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "loads"


def test_missing_metadata_is_rejected() -> None:
    response = MCPServer(name="loads").handle({"id": 1, "method": "tools/list"})
    assert response.error.code == JSONRPCErrorCode.UNSUPPORTED_PROTOCOL_VERSION


def test_unsupported_version_includes_supported_versions() -> None:
    request = modern("server/discover")
    request["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] = "1900-01-01"
    response = MCPServer(name="loads").handle(request)
    assert response.error.code == JSONRPCErrorCode.UNSUPPORTED_PROTOCOL_VERSION
    assert response.error.data["supported"] == ["2026-07-28"]


def test_unknown_method_is_method_not_found() -> None:
    response = MCPServer(name="loads").handle(modern("missing"))
    assert response.error.code == JSONRPCErrorCode.METHOD_NOT_FOUND


def test_async_dispatch_is_available() -> None:
    async def run() -> None:
        response = await MCPServer(name="loads").handle_async(modern("server/discover"))
        assert response.error is None

    asyncio.run(run())


def test_unexpected_exception_returns_generic_message() -> None:
    server = MCPServer(name="loads")

    @server.tool()
    def broken() -> str:
        raise RuntimeError("database password=secret")

    response = server.handle(modern("tools/call", params={"name": "broken"}))
    assert response.error.message == "Internal server error"
    assert "secret" not in response.error.message
