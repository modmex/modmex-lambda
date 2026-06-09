"""API Gateway event handler public API."""

from __future__ import annotations

import re
import json
from typing import Any, Callable, Pattern
from functools import partial
from enum import Enum
from http import HTTPStatus

from modmex_lambda.event_handler import content_types
from modmex_lambda.event_handler.exceptions import (
    ForbiddenError,
    MethodNotAllowedError,
    NotFoundError,
    RequestValidationError,
    UnauthorizedError,
)
from modmex_lambda.event_handler.gateway_response import GatewayResponseBuilder
from modmex_lambda.event_handler.request import Request
from modmex_lambda.event_handler.response import Response
from modmex_lambda.event_handler.routing import HasRoutes, Route, Router
from modmex_lambda.event_handler.routing_fallbacks import RoutingFallbackHandler
from modmex_lambda.data_classes.common import BaseProxyEvent
from modmex_lambda.data_classes.api_gateway_proxy_event import APIGatewayProxyEvent, APIGatewayProxyEventV2
from modmex_lambda.shared.types import AnyCallableT
from modmex_lambda.event_handler.types import IApiGatewayResolver
from modmex_lambda.event_handler.dependencies.dependency_middleware import DependencyMiddleware
from modmex_lambda.event_handler.dependencies.depends import DefaultDependencyResolver, DependencyResolver
from modmex_lambda.event_handler.middlewares import NextMiddleware
from modmex_lambda.event_handler.cors import CORSConfig
from modmex_lambda.shared.json_encoder import JSONEncoder
from modmex_lambda.event_handler.constants import DEFAULT_STATUS_CODE

# NextMiddleware = Callable[["ApiGatewayResolver"], Response]
Middleware = Callable[["ApiGatewayResolver", NextMiddleware], Response]


JSON_DUMP_CALL = partial(json.dumps, separators=(",", ":"), cls=JSONEncoder)


class ProxyEventType(Enum):
    """An enumerations of the supported proxy event types."""

    APIGatewayProxyEvent = "APIGatewayProxyEvent"
    APIGatewayProxyEventV2 = "APIGatewayProxyEventV2"
    LambdaFunctionUrlEvent = "LambdaFunctionUrlEvent"


_PROXY_EVENT_MAP: dict[Enum, type[BaseProxyEvent]] = {
    ProxyEventType.APIGatewayProxyEvent: APIGatewayProxyEvent,
    ProxyEventType.APIGatewayProxyEventV2: APIGatewayProxyEventV2,
    ProxyEventType.LambdaFunctionUrlEvent: APIGatewayProxyEventV2,
}


class BaseRouter(HasRoutes):
    current_event: BaseProxyEvent
    lambda_context: object
    context: dict[str, Any]
    _router_middlewares: list[Callable] = []
    processed_stack_frames: list[str] = []
    
    def use(self, middlewares: list[Middleware]) -> None:
        self._router_middlewares = self._router_middlewares + middlewares

    def append_context(self, **kwargs: Any) -> None:
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """Resets routing context"""
        self.context.clear()

    @property
    def request(self) -> Request:
        cached: Request | None = self.context.get("_request")
        if cached is not None:
            return cached

        route: Route | None = self.context.get("_route")
        if route is None:
            raise RuntimeError(
                "app.request is only available after route resolution. Use it inside middleware or a route handler.",
            )

        request = Request(
            route_path=route.path,
            path_parameters=self.context.get("_path_params", {}),
            current_event=self.current_event,
            context=self.context,
        )
        self.context["_request"] = request
        return request


class ApiGatewayResolver(BaseRouter, IApiGatewayResolver):
    _event_type: ProxyEventType

    def __init__(
        self,
        *,
        cors: CORSConfig | None = None,
        serializer: Callable[[dict], str] | None = None,
        strip_prefixes: list[str | Pattern] | None = None,
        json_body_deserializer: Callable[[str], dict] | None = None,
        logger: Any | None = None,
        dependency_resolver: DependencyResolver | None = None,
    ) -> None:
        self._cors = cors
        self._cors_enabled = cors is not None
        
        self._router = Router()
        self._routing_fallbacks = RoutingFallbackHandler(self)
        self._response_builder_class = GatewayResponseBuilder
        
        self._serializer = serializer or JSON_DUMP_CALL
        self._json_body_deserializer = json_body_deserializer
        
        self._router_middlewares: list[Middleware] = []

        self._logger = logger
        self.dependency_resolver = dependency_resolver or DefaultDependencyResolver()
        self.dependency_overrides: dict[Callable[..., Any], Callable[..., Any]] = {}
        self.current_event = None
        self.current_context = None
        self._strip_prefixes = strip_prefixes
        self.context: dict[str, Any] = {}
        self._dependency_middleware = DependencyMiddleware()


    @property
    def handler(self) -> Callable[[dict[str, Any], object], dict[str, Any]]:
        return self.resolve

    def middleware(self, func: Middleware | None = None) -> Any:
        if func is None:
            def decorator(mw: Middleware) -> Middleware:
                self._router_middlewares.append(mw)
                return mw

            return decorator

        self._router_middlewares.append(func)
        return func

    def route(
        self,
        rule: str,
        method: str | list[str] | tuple[str],
        description: str | None = None,
        status_code: int | None = DEFAULT_STATUS_CODE,
        middlewares: list[Middleware] | None = None,
        cors: bool | None = None,
        compress: bool = False,
        cache_control: str | None = None,
        **_: Any,
    ) -> Callable[[AnyCallableT], AnyCallableT]:
        cors_enabled = self._cors_enabled if cors is None else cors
        return self._router.route(
            rule=rule,
            method=method,
            description=description,
            status_code=status_code,
            middlewares=middlewares,
            cors=cors_enabled,
            compress=compress,
            cache_control=cache_control,
        )

    def include_router(self, router: Router) -> None:
        self._router.include_router(router)

    def resolve(self, event: dict[str, Any], context: object) -> dict[str, Any]:
        self.current_event = self._to_proxy_event(event)
        self.current_context = context
        self.context = {}
        response = self._resolve().serialize(self.current_event, self._cors)
        self.clear_context()
        return response

    def _resolve(self) -> GatewayResponseBuilder:
        path = self._remove_prefix(self.current_event.path)
        method = self.current_event.http_method.upper()
        route, path_params, allowed_methods = self._router.match(method, path)
    
        if route:
            self.append_context(
                _route=route,
                _route_args=path_params,
                _path_params=path_params,
                _path=path,
            )
            
            response = self._call_route(route, route_arguments=path_params)
        elif allowed_methods:
            response = self._routing_fallbacks.method_not_allowed(
                method=method,
                path=path,
                allowed_methods=allowed_methods,
            )
        else:
            response = self._routing_fallbacks.not_found(method=method, path=path)
            
        return self._response_builder_class(
            response=response,
            route=route,
            json_serializer=self._serializer,
        )

    def _call_route(self, route: Route, route_arguments: dict | None = None) -> Response:
        try:
            response = route.invoke(
                router_middlewares=self._router_middlewares,
                app=self,
                route_arguments=route_arguments or {},
            )
            return response
        except Exception as e:
            response = self._call_exception_handler(e)
            if response:
                return response
            
            raise

    def _remove_prefix(self, path: str) -> str:
        """Remove the configured prefix from the path"""
        if not isinstance(self._strip_prefixes, list):
            return path

        for prefix in self._strip_prefixes:
            if isinstance(prefix, str):
                if path == prefix:
                    return "/"

                if self._path_starts_with(path, prefix):
                    return path[len(prefix) :]

            if isinstance(prefix, Pattern):
                path = re.sub(prefix, "", path)

                if not path:
                    return "/"

        return path

    def _to_proxy_event(self, event: dict) -> BaseProxyEvent:
        event_type = getattr(self, "_event_type", None)
        if event_type is None:
            raise TypeError(
                "ApiGatewayResolver is a base resolver. Use ApiGatewayRestResolver for API Gateway REST API "
                "payload v1 or ApiGatewayHttpResolver for API Gateway HTTP API payload v2.",
            )

        event_class = _PROXY_EVENT_MAP.get(event_type)
        if event_class is None:
            raise TypeError(f"Unsupported API Gateway event type: {event_type!r}")

        return event_class(event, self._json_body_deserializer)

    def _to_response(self, result: dict | tuple | Response) -> Response:
        if isinstance(result, Response):
            return result
        if isinstance(result, tuple) and len(result) == 2:
            result, status_code = result
        else:
            route: Route | None = self.context.get("_route")
            status_code = route.status_code if route else HTTPStatus.OK.value
        return Response(body=result, status_code=status_code, content_type=content_types.APPLICATION_JSON)

    def exception_handler(
        self,
        exc_class: type[Exception] | list[type[Exception]],
    ):
        return self._router.exception_handler(exc_class)
    
    def _call_exception_handler(self, exp: Exception) -> Response | None:
        handler = self._router.exception_handler_manager.lookup_exception_handler(type(exp))
        if handler:
            try:
                return handler(exp)
            except Exception as exc:
                exp = exc

        return self._default_error_response(exp)

    def _default_error_response(self, exc: Exception) -> Response | None:
        if isinstance(exc, RequestValidationError):
            errors = [{"loc": e["loc"], "type": e["type"]} for e in exc.errors()]
            return Response(
                body={
                    "message": "Validation Error",
                    "detail": errors,
                },
                status_code=HTTPStatus.BAD_REQUEST.value,
                content_type=content_types.APPLICATION_JSON,
            )
        if isinstance(exc, MethodNotAllowedError):
            return Response(body={"message": "Method Not Allowed"}, status_code=405)
        if isinstance(exc, NotFoundError):
            return Response(body={"message": "Not Found"}, status_code=404)
        if isinstance(exc, UnauthorizedError):
            return Response(body={"message": "Unauthorized"}, status_code=401)
        if isinstance(exc, ForbiddenError):
            return Response(body={"message": "Forbidden"}, status_code=403)
        return None

    @staticmethod
    def _path_starts_with(path: str, prefix: str) -> bool:
        """Returns true if the `path` starts with a prefix plus a `/`"""
        if not isinstance(prefix, str) or prefix == "":
            return False

        return path.startswith(f"{prefix}/")

class ApiGatewayRestResolver(ApiGatewayResolver):
    """Resolver for API Gateway REST API payload v1."""

    _event_type = ProxyEventType.APIGatewayProxyEvent


class ApiGatewayHttpResolver(ApiGatewayResolver):
    """Resolver for API Gateway HTTP API payload v2."""

    _event_type = ProxyEventType.APIGatewayProxyEventV2


__all__ = [
    "ApiGatewayHttpResolver",
    "ApiGatewayRestResolver",
    "Request",
    "Response",
    "Route",
]
