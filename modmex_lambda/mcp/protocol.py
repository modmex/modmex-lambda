"""Small, transport-neutral JSON-RPC models used by the MCP server."""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Dict, Literal, Optional, Union

from modmex import BaseModel


JSONRPCVersion = Literal["2.0"]
JSONRPCId = Optional[Union[str, int]]
MCP_PROTOCOL_VERSION = "2026-07-28"


class JSONRPCErrorCode(IntEnum):
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    HEADER_MISMATCH = -32020
    UNSUPPORTED_PROTOCOL_VERSION = -32022


class JSONRPCRequest(BaseModel):
    jsonrpc: JSONRPCVersion = "2.0"
    id: JSONRPCId = None
    method: str
    params: Optional[Dict[str, Any]] = None

    @property
    def metadata(self) -> dict[str, Any]:
        return (self.params or {}).get("_meta", {})


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Any = None


class JSONRPCResponse(BaseModel):
    jsonrpc: JSONRPCVersion = "2.0"
    id: JSONRPCId = None
    result: Any = None
    error: Optional[JSONRPCError] = None

    @classmethod
    def success(cls, request_id: JSONRPCId, result: Any = None) -> "JSONRPCResponse":
        return cls(id=request_id, result=result)

    @classmethod
    def failure(
        cls,
        request_id: JSONRPCId,
        code: int | JSONRPCErrorCode,
        message: str,
        data: Any = None,
    ) -> "JSONRPCResponse":
        return cls(
            id=request_id,
            error=JSONRPCError(code=int(code), message=message, data=data),
        )
