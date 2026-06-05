"""API Gateway WebSocket event data class."""

from __future__ import annotations

import json
from typing import Any

from modmex_lambda.data_classes.common import DictWrapper


class APIGatewayWebSocketEvent(DictWrapper):
    @property
    def request_context(self) -> dict[str, Any]:
        return dict(self.get("requestContext") or {})

    @property
    def route_key(self) -> str:
        return str((self.request_context or {}).get("routeKey") or "")

    @property
    def event_type(self) -> str:
        return str((self.request_context or {}).get("eventType") or "")

    @property
    def connection_id(self) -> str:
        return str((self.request_context or {}).get("connectionId") or "")

    @property
    def body(self) -> Any:
        return self.get("body")

    @property
    def json_body(self) -> Any:
        body = self.body
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return body
        return body
