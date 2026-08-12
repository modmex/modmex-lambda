from __future__ import annotations

import json
from typing import Annotated

from modmex_lambda import APIGatewayHttpResolver, Depends, Request
from modmex_lambda.mcp import MCPServer, MCPStreamingHttpTransport
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


def test_mcp_accepts_lambda_function_url_payload_format_v2() -> None:
    """Function URLs use the same HTTP API v2 event shape as HTTP API."""
    app = APIGatewayHttpResolver()
    app.include_mcp(MCPServer(name="function-url", version="1.0.0"), path="/mcp")
    request = modern("server/discover")
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/mcp",
        "rawQueryString": "",
        "headers": {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "mcp-protocol-version": "2026-07-28",
            "mcp-method": "server/discover",
            "host": "example.lambda-url.us-east-1.on.aws",
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "example",
            "domainName": "example.lambda-url.us-east-1.on.aws",
            "domainPrefix": "example",
            "http": {
                "method": "POST",
                "path": "/mcp",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            },
            "requestId": "request-1",
            "routeKey": "$default",
            "stage": "$default",
            "time": "12/Aug/2026:19:00:00 +0000",
            "timeEpoch": 1786561200000,
        },
        "body": json.dumps(request),
        "pathParameters": None,
        "isBase64Encoded": False,
    }

    response = app.resolve(event, object())

    assert response["statusCode"] == 200
    assert response_body(response)["result"]["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "function-url"


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


def test_mcp_validates_tool_parameter_headers_against_arguments() -> None:
    app = APIGatewayHttpResolver()
    server = MCPServer(name="loads")

    @server.tool()
    def lookup(region: str, enabled: bool = False) -> dict:
        return {"region": region, "enabled": enabled}

    app.include_mcp(server)
    base_headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "lookup"}
    tool = server.tools.get("lookup")
    original_definition = tool.definition
    definition = original_definition()
    definition["inputSchema"]["properties"]["region"]["x-mcp-header"] = "Region"
    definition["inputSchema"]["properties"]["enabled"]["x-mcp-header"] = "Enabled"
    tool.definition = lambda: definition
    payload = modern("tools/call", params={"name": "lookup", "arguments": {"region": "us-west1", "enabled": True}})

    missing = app.resolve(http_v2_event("POST", "/mcp", headers=base_headers, body=payload), object())
    assert missing["statusCode"] == 400
    assert response_body(missing)["error"]["code"] == -32020

    valid = app.resolve(http_v2_event("POST", "/mcp", headers={**base_headers, "Mcp-Param-Region": "us-west1", "Mcp-Param-Enabled": "true"}, body=payload), object())
    assert valid["statusCode"] == 200

    tampered = app.resolve(http_v2_event("POST", "/mcp", headers={**base_headers, "Mcp-Param-Region": "eu-west1", "Mcp-Param-Enabled": "true"}, body=payload), object())
    assert tampered["statusCode"] == 400
    assert response_body(tampered)["error"]["code"] == -32020


def test_mcp_validates_encoded_parameter_header_values() -> None:
    app = APIGatewayHttpResolver()
    server = MCPServer(name="loads")

    @server.tool()
    def lookup(region: str) -> str:
        return region

    app.include_mcp(server)
    tool = server.tools.get("lookup")
    definition = tool.definition()
    definition["inputSchema"]["properties"]["region"]["x-mcp-header"] = "Region"
    tool.definition = lambda: definition
    import base64
    encoded = "=?base64?" + base64.b64encode("Hello, 世界".encode()).decode() + "?="
    headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "lookup", "Mcp-Param-Region": encoded}
    payload = modern("tools/call", params={"name": "lookup", "arguments": {"region": "Hello, 世界"}})
    response = app.resolve(http_v2_event("POST", "/mcp", headers=headers, body=payload), object())
    assert response["statusCode"] == 200


def test_streaming_transport_emits_mcp_response_as_sse() -> None:
    server = MCPServer(name="loads")
    transport = MCPStreamingHttpTransport(server)
    payload = modern("server/discover")

    class Request:
        json_body = payload
        headers = {
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": "2026-07-28",
            "mcp-method": "server/discover",
        }

    response = transport.handle(Request())
    assert response.status_code == 200
    assert response.content_type == "text/event-stream"
    body = "".join(response.body)
    assert '"jsonrpc":"2.0"' in body
    assert '"resultType":"complete"' in body


def test_streaming_transport_preserves_header_validation_response() -> None:
    transport = MCPStreamingHttpTransport(MCPServer(name="loads"))
    payload = modern("server/discover")

    class Request:
        json_body = payload
        headers = {"accept": "application/json"}

    response = transport.handle(Request())
    assert response.status_code == 406
    assert "Accept must include" in "".join(response.body)


def test_streaming_transport_emits_progress_before_tool_result() -> None:
    server = MCPServer(name="loads")

    @server.tool()
    def long_running(ctx) -> dict[str, str]:
        assert ctx.progress is not None
        ctx.progress.report(1, total=2, message="started")
        ctx.progress.report(2, total=2, message="finished")
        return {"status": "done"}

    transport = MCPStreamingHttpTransport(server)
    payload = modern("tools/call", params={"name": "long_running", "arguments": {}})

    class Request:
        json_body = payload
        headers = {
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": "2026-07-28",
            "mcp-method": "tools/call",
            "mcp-name": "long_running",
        }

    response = transport.handle(Request())
    events = list(response.body)
    assert len(events) == 3
    assert 'event: progress' in events[0]
    assert '"progress":1' in events[0]
    assert '"progress":2' in events[1]
    assert 'status' in events[2]
