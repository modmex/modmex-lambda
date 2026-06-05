"""API Gateway proxy response building."""

from __future__ import annotations

import base64
import zlib
from collections.abc import Callable, Mapping
from typing import Any

from modmex_lambda.data_classes.common import BaseProxyEvent
from modmex_lambda.event_handler.cors import CORSConfig
from modmex_lambda.event_handler.response import Response
from modmex_lambda.event_handler.routing import Route


class GatewayResponseBuilder:
    def __init__(self, response: Response, route: Route | None, json_serializer: Callable[[Any], str]) -> None:
        self.response = response
        self.route = route
        self.json_serializer = json_serializer

    def serialize(self, event: BaseProxyEvent, cors: CORSConfig | None = None) -> dict[str, Any]:
        if self.response.is_json() and not isinstance(self.response.body, (str, bytes)):
            self.response.body = self.json_serializer(self.response.body)

        self._handle_route_configuration(event, cors)

        if isinstance(self.response.body, bytes):
            self.response.base64_encoded = True
            self.response.body = base64.b64encode(self.response.body).decode()

        return {
            "statusCode": self.response.status_code,
            "body": self.response.body,
            "isBase64Encoded": self.response.base64_encoded,
            **event.header_serializer().serialize(
                headers=self.response.headers,
                cookies=self.response.cookies,
            ),
        }

    def _handle_route_configuration(self, event: BaseProxyEvent, cors: CORSConfig | None) -> None:
        if self.route is None:
            return
        if self.route.cors:
            self._add_cors(event, cors or CORSConfig())
        if self.route.cache_control:
            self._add_cache_control(self.route.cache_control)
        if self._compression_enabled(
            route_compression=self.route.compress,
            response_compression=self.response.compress,
            event=event,
        ):
            self._compress()

    def _add_cors(self, event: BaseProxyEvent, cors: CORSConfig) -> None:
        origin_header = self._extract_origin_header(event.resolved_headers_field)
        origin = cors.allowed_origin(origin_header)
        if origin is not None:
            self.response.headers.update(cors.to_dict(origin))

    def _add_cache_control(self, cache_control: str) -> None:
        self.response.headers["Cache-Control"] = cache_control if self.response.status_code == 200 else "no-cache"

    def _compress(self) -> None:
        self.response.headers["Content-Encoding"] = "gzip"
        if isinstance(self.response.body, str):
            self.response.body = bytes(self.response.body, "utf-8")
        gzip = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
        self.response.body = gzip.compress(self.response.body) + gzip.flush()

    @staticmethod
    def _extract_origin_header(resolved_headers: Mapping[str, Any]) -> str | None:
        resolved_header = resolved_headers.get("origin")
        if isinstance(resolved_header, list):
            return resolved_header[0]
        return resolved_header

    @staticmethod
    def _compression_enabled(
        route_compression: bool,
        response_compression: bool | None,
        event: BaseProxyEvent,
    ) -> bool:
        encoding = event.resolved_headers_field.get("accept-encoding", "")
        if isinstance(encoding, list):
            encoding = ",".join(encoding)

        if not isinstance(encoding, str) or "gzip" not in encoding:
            return False
        if response_compression is not None:
            return response_compression
        return route_compression


__all__ = ["GatewayResponseBuilder"]
