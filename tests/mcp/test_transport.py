from __future__ import annotations

from modmex_lambda import APIGatewayHttpResolver
from modmex_lambda.mcp import MCPServer, SSEEvent, encode_sse, encode_sse_stream
from tests.conftest import http_v2_event
from tests.mcp.helpers import modern


def test_encode_sse_supports_metadata_and_multiline_data() -> None:
    encoded = encode_sse(SSEEvent(
        data="one\ntwo",
        event="message",
        event_id="evt-1",
        retry=1000,
    ))

    assert encoded == 'id: evt-1\nevent: message\nretry: 1000\ndata: one\ndata: two\n\n'


def test_encode_sse_stream_preserves_event_order() -> None:
    assert encode_sse_stream([{"n": 1}, {"n": 2}]) == 'data: {"n":1}\n\ndata: {"n":2}\n\n'


def test_mcp_http_route_negotiates_sse_using_existing_request_headers() -> None:
    app = APIGatewayHttpResolver()
    app.include_mcp(MCPServer(name="loads"))
    response = app.resolve(http_v2_event(
        "POST",
        "/mcp",
        headers={"Accept": "text/event-stream, application/json", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "server/discover"},
        body=modern("server/discover"),
    ), object())

    assert response["headers"]["Content-Type"] == "text/event-stream"
    assert response["headers"]["Cache-Control"] == "no-cache"
    assert response["body"].startswith('data: {"jsonrpc":"2.0","id":1,"result":')
