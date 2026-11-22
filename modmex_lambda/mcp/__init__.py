"""MCP server, protocol, and HTTP transport primitives."""

from modmex_lambda.mcp.protocol import (
    MCP_PROTOCOL_VERSION,
    JSONRPCError,
    JSONRPCErrorCode,
    JSONRPCRequest,
    JSONRPCResponse,
)
from modmex_lambda.mcp.server import MCPError, MCPServer
from modmex_lambda.mcp.tool import MCPTool
from modmex_lambda.mcp.resource import MCPResource
from modmex_lambda.mcp.prompt import MCPPrompt
from modmex_lambda.mcp.transport import MCPHttpTransport, MCPStreamingHttpTransport, StreamingHTTPResponse, SSEEvent, encode_sse, encode_sse_stream, MCP_JSON_CONTENT_TYPE, MCP_SSE_CONTENT_TYPE
from modmex_lambda.mcp.middleware import MCPContext, MCPMiddleware, MCPNextMiddleware, MCPProgressReporter, MCPCancellationToken

__all__ = [
    "JSONRPCError",
    "JSONRPCErrorCode",
    "MCP_PROTOCOL_VERSION",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "MCPServer",
    "MCPError",
    "MCPHttpTransport",
    "MCPStreamingHttpTransport",
    "StreamingHTTPResponse",
    "MCPTool",
    "MCPResource",
    "MCPPrompt",
    "SSEEvent",
    "encode_sse",
    "encode_sse_stream",
    "MCP_JSON_CONTENT_TYPE",
    "MCP_SSE_CONTENT_TYPE",
    "MCPContext",
    "MCPMiddleware",
    "MCPNextMiddleware",
    "MCPProgressReporter",
    "MCPCancellationToken",
    "LambdaWebAdapterResolver",
]


def __getattr__(name):
    # LambdaWebAdapterResolver pulls in http.server and is only needed with the
    # Lambda Web Adapter; load it on first access, not with every MCP import.
    if name == "LambdaWebAdapterResolver":
        from modmex_lambda.mcp.web_adapter import LambdaWebAdapterResolver

        globals()[name] = LambdaWebAdapterResolver
        return LambdaWebAdapterResolver
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
