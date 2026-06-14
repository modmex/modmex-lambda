from __future__ import annotations

from typing import Any, Callable, TypeVar, Union

from abc import ABC
from modmex_lambda.data_classes.api_gateway_proxy_event import APIGatewayProxyEvent, APIGatewayProxyEventV2
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.event_handler.request import Request
from modmex_lambda.event_handler.response import Response


class IApiGatewayResolver(ABC):
    context: dict[str, Any]
    current_event: Union[APIGatewayProxyEvent, APIGatewayProxyEventV2]
    dependency_resolver: DependencyResolver
    dependency_overrides: dict[Callable[..., Any], Callable[..., Any]]
    _dependency_middleware: Callable[..., Any]

    @property
    def request(self) -> Request:
        raise NotImplementedError

    def resolve(self, event: dict[str, Any], context: object) -> dict[str, Any]:
        raise NotImplementedError()

    def append_context(self, **kwargs: Any) -> None:
        raise NotImplementedError

    def _to_response(self, result: dict | tuple | Response) -> Response:
        raise NotImplementedError


EventHandlerInstance = TypeVar("EventHandlerInstance", bound=IApiGatewayResolver)
