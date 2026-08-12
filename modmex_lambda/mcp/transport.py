"""MCP HTTP transport encoders for JSON and Server-Sent Events."""

from __future__ import annotations

import json
import base64
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Iterable


MCP_JSON_CONTENT_TYPE = "application/json"
MCP_SSE_CONTENT_TYPE = "text/event-stream"


@dataclass(frozen=True)
class SSEEvent:
    data: Any
    event: str | None = None
    event_id: str | None = None
    retry: int | None = None


def encode_sse(event: SSEEvent | Any) -> str:
    """Encode one event according to the SSE wire format."""
    if not isinstance(event, SSEEvent):
        event = SSEEvent(data=event)
    lines: list[str] = []
    if event.event_id is not None:
        lines.append(f"id: {event.event_id}")
    if event.event is not None:
        lines.append(f"event: {event.event}")
    if event.retry is not None:
        lines.append(f"retry: {event.retry}")
    payload = event.data if isinstance(event.data, str) else json.dumps(event.data, separators=(",", ":"), default=_serialize)
    lines.extend(f"data: {line}" for line in payload.splitlines() or [""])
    return "\n".join(lines) + "\n\n"


def encode_sse_stream(events: Iterable[SSEEvent | Any]) -> str:
    return "".join(encode_sse(event) for event in events)


class MCPHttpTransport:
    """Bind an MCP server to an HTTP request/response abstraction.

    The transport owns MCP HTTP headers, content negotiation, JSON-RPC
    dispatch, and JSON/SSE framing. Host adapters only need to provide a
    request with ``json_body`` and ``headers`` and return the resulting
    response object.
    """

    def __init__(self, server: Any, *, allowed_origins: list[str] | None = None) -> None:
        self.server = server
        self.allowed_origins = set(allowed_origins or [])

    def handle(self, request: Any) -> Any:
        from modmex_lambda.event_handler import content_types
        from modmex_lambda.event_handler.response import Response
        from modmex_lambda.mcp import JSONRPCErrorCode, JSONRPCResponse

        try:
            payload = request.json_body
        except Exception as exc:
            response = JSONRPCResponse.failure(None, JSONRPCErrorCode.PARSE_ERROR, str(exc))
            return Response(body=self._model_dict(response), status_code=HTTPStatus.OK, content_type=MCP_JSON_CONTENT_TYPE)

        origin = request.headers.get("origin")
        if origin and self.allowed_origins and origin not in self.allowed_origins:
            return Response(body={"error": "Origin is not allowed"}, status_code=HTTPStatus.FORBIDDEN, content_type=content_types.APPLICATION_JSON)
        if isinstance(payload, list):
            return Response(body={"error": "Batch requests are not supported by Streamable HTTP"}, status_code=HTTPStatus.BAD_REQUEST, content_type=content_types.APPLICATION_JSON)
        if isinstance(payload, dict):
            validation_error = self._validate_headers(payload, request.headers)
            if validation_error is not None:
                return validation_error

        response = self.server.handle(payload, context=request)
        body = self._model_dict(response) if response is not None else None

        wants_sse = self._accepts_sse(request.headers.get("accept"))
        response_headers = {"MCP-Protocol-Version": "2026-07-28"}
        if wants_sse:
            response_headers.update({"Cache-Control": "no-cache", "Connection": "keep-alive"})
            if body is not None:
                body = encode_sse(body)
        status_code = HTTPStatus.ACCEPTED if response is None else HTTPStatus.OK
        if response is not None and response.error is not None and response.error.code == JSONRPCErrorCode.METHOD_NOT_FOUND:
            status_code = HTTPStatus.NOT_FOUND
        return Response(
            body=body,
            status_code=status_code,
            content_type=MCP_SSE_CONTENT_TYPE if wants_sse else MCP_JSON_CONTENT_TYPE,
            headers=response_headers,
        )

    def _validate_headers(self, payload: dict[str, Any], headers: Any) -> Any:
        from modmex_lambda.event_handler import content_types
        from modmex_lambda.event_handler.response import Response
        from modmex_lambda.mcp import JSONRPCErrorCode, JSONRPCResponse

        method = payload.get("method")
        accept = headers.get("accept")
        if not isinstance(accept, str) or MCP_JSON_CONTENT_TYPE not in accept.lower() or MCP_SSE_CONTENT_TYPE not in accept.lower():
            return Response(body={"error": "Accept must include application/json and text/event-stream"}, status_code=HTTPStatus.NOT_ACCEPTABLE, content_type=content_types.APPLICATION_JSON)
        protocol = headers.get("mcp-protocol-version")
        if protocol != "2026-07-28":
            response = JSONRPCResponse.failure(payload.get("id"), JSONRPCErrorCode.UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version", {"supported": ["2026-07-28"], "requested": protocol})
            return Response(body=self._model_dict(response), status_code=HTTPStatus.BAD_REQUEST, content_type=content_types.APPLICATION_JSON)
        if protocol != (payload.get("params") or {}).get("_meta", {}).get("io.modelcontextprotocol/protocolVersion"):
            return self._header_mismatch(payload, "MCP-Protocol-Version does not match _meta protocolVersion")
        if headers.get("mcp-method") != method:
            return self._header_mismatch(payload, "Mcp-Method does not match request method")
        expected_name = {"tools/call": (payload.get("params") or {}).get("name"), "prompts/get": (payload.get("params") or {}).get("name"), "resources/read": (payload.get("params") or {}).get("uri")}.get(method)
        if expected_name is not None and self._decode_header(headers.get("mcp-name")) != expected_name:
            return self._header_mismatch(payload, "Mcp-Name does not match request name")
        metadata = (payload.get("params") or {}).get("_meta", {})
        if "io.modelcontextprotocol/clientCapabilities" not in metadata:
            response = JSONRPCResponse.failure(payload.get("id"), JSONRPCErrorCode.INVALID_PARAMS, "Missing clientCapabilities")
            return Response(body=self._model_dict(response), status_code=HTTPStatus.BAD_REQUEST, content_type=content_types.APPLICATION_JSON)
        return None

    def _header_mismatch(self, payload: dict[str, Any], message: str) -> Any:
        from modmex_lambda.event_handler.response import Response
        from modmex_lambda.mcp import JSONRPCErrorCode, JSONRPCResponse
        response = JSONRPCResponse.failure(payload.get("id"), JSONRPCErrorCode.HEADER_MISMATCH, message)
        return Response(body=self._model_dict(response), status_code=HTTPStatus.BAD_REQUEST, content_type=MCP_JSON_CONTENT_TYPE)

    @staticmethod
    def _decode_header(value: Any) -> Any:
        if not isinstance(value, str) or not value.startswith("=?base64?") or not value.endswith("?="):
            return value
        try:
            return base64.b64decode(value[9:-2]).decode()
        except (ValueError, UnicodeDecodeError):
            return value

    @staticmethod
    def _model_dict(value: Any) -> dict[str, Any]:
        return {key: item for key, item in value.model_dump().items() if item is not None}

    @staticmethod
    def _accepts_sse(value: Any) -> bool:
        if isinstance(value, list):
            value = ",".join(value)
        if not isinstance(value, str):
            return False
        accepted = value.lower()
        # Honor the client's ordering preference while requiring both media
        # types for Streamable HTTP compliance.
        return (
            MCP_SSE_CONTENT_TYPE in accepted
            and MCP_JSON_CONTENT_TYPE in accepted
            and accepted.index(MCP_SSE_CONTENT_TYPE) < accepted.index(MCP_JSON_CONTENT_TYPE)
        )


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)
