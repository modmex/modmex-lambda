import subprocess
import sys

from modmex_lambda import APIGatewayHttpResolver
from modmex_lambda.mcp import MCPServer
from tests.conftest import http_v2_event
from tests.mcp.helpers import modern


def _event(origin):
    headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "server/discover"}
    if origin:
        headers["Origin"] = origin
    return http_v2_event("POST", "/mcp", headers=headers, body=modern("server/discover"))


def test_include_mcp_enforces_allowed_origins():
    app = APIGatewayHttpResolver()
    app.include_mcp(MCPServer(name="t"), allowed_origins=["https://app.example.com"])
    assert app.resolve(_event("https://evil.example"), None)["statusCode"] == 403
    assert app.resolve(_event("https://app.example.com"), None)["statusCode"] == 200


def test_mcp_import_does_not_load_the_web_adapter():
    code = "import sys, modmex_lambda.mcp; print('modmex_lambda.mcp.web_adapter' in sys.modules, 'http.server' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.split()
    assert out == ["False", "False"]
    from modmex_lambda.mcp import LambdaWebAdapterResolver  # still importable on demand
    assert LambdaWebAdapterResolver.__name__ == "LambdaWebAdapterResolver"
