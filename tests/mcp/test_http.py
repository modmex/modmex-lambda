from __future__ import annotations

from typing import Annotated

from modmex_lambda import APIGatewayHttpResolver, Depends, Request
from modmex_lambda.mcp import MCPServer
from tests.conftest import http_v2_event, response_body
from tests.mcp.helpers import modern


class Service:
    def method(self, request_id: str) -> str:
        return request_id


def test_include_mcp_uses_existing_api_gateway_resolver() -> None:
    app = APIGatewayHttpResolver()
    app.include_mcp(MCPServer(name="loads", version="1.0.0"), path="/mcp")
    request = modern("server/discover")
    response = app.resolve(http_v2_event("POST", "/mcp", headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "server/discover"}, body=request), object())
    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/json"
    assert response_body(response)["result"]["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "loads"


def test_mcp_route_reuses_request_context_and_tool_di() -> None:
    app = APIGatewayHttpResolver()
    server = MCPServer(name="loads")

    @server.tool()
    def request_info(service: Annotated[Service, Depends()], request: Request) -> dict:
        return {"method": request.method, "value": service.method(request.method)}

    app.include_mcp(server)
    response = app.resolve(http_v2_event("POST", "/mcp", headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "request_info"}, body=modern("tools/call", params={"name": "request_info", "arguments": {}})), object())
    assert response_body(response)["result"]["isError"] is False


def test_mcp_method_routing_and_http_method_use_gateway_pipeline() -> None:
    app = APIGatewayHttpResolver()
    app.include_mcp(MCPServer(name="loads"))
    response = app.resolve(http_v2_event("POST", "/mcp", headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "server/discover"}, body=modern("server/discover")), object())
    assert response_body(response)["result"]["resultType"] == "complete"
    not_allowed = app.resolve(http_v2_event("GET", "/mcp"), object())
    assert not_allowed["statusCode"] == 405


def test_mcp_rejects_mismatched_modern_headers() -> None:
    app = APIGatewayHttpResolver()
    app.include_mcp(MCPServer(name="loads"))
    response = app.resolve(http_v2_event(
        "POST",
        "/mcp",
        headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"},
        body=modern("server/discover"),
    ), object())
    assert response["statusCode"] == 400
