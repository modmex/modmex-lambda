"""API Gateway Lambda authorizer event data class."""

from __future__ import annotations

from typing import Any

from modmex_lambda.data_classes.common import DictWrapper


class APIGatewayAuthorizerEvent(DictWrapper):
    @property
    def type(self) -> str:
        return str(self.get("type") or "")

    @property
    def method_arn(self) -> str:
        return str(self.get("methodArn") or "")

    @property
    def authorization_token(self) -> str | None:
        value = self.get("authorizationToken")
        return None if value is None else str(value)

    @property
    def headers(self) -> dict[str, Any]:
        return dict(self.get("headers") or {})

    @property
    def query_string_parameters(self) -> dict[str, Any]:
        return dict(self.get("queryStringParameters") or {})

    @property
    def path_parameters(self) -> dict[str, Any]:
        return dict(self.get("pathParameters") or {})

    @property
    def request_context(self) -> dict[str, Any]:
        return dict(self.get("requestContext") or {})
