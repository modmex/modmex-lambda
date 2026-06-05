"""Synthetic fallback routes for API Gateway routing misses."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Callable

from modmex_lambda.event_handler import content_types
from modmex_lambda.event_handler.cors import CORSConfig
from modmex_lambda.event_handler.exceptions import MethodNotAllowedError, NotFoundError
from modmex_lambda.event_handler.response import Response
from modmex_lambda.event_handler.routing import Route

if TYPE_CHECKING:
    from modmex_lambda.event_handler.api_gateway import ApiGatewayResolver


class RoutingFallbackHandler:
    def __init__(self, app: ApiGatewayResolver) -> None:
        self.app = app

    def not_found(self, method: str, path: str) -> Response:
        def not_found_handler() -> Response:
            if self.app._cors_enabled and method == "OPTIONS":
                return self._preflight_response(self.app._router.cors_methods)

            custom_response = self._custom_response(NotFoundError)
            if custom_response is not None:
                return custom_response

            return self._not_found_response()

        return self._call_synthetic_route(method=method, path=path, handler=not_found_handler)

    def method_not_allowed(self, method: str, path: str, allowed_methods: set[str]) -> Response:
        def method_not_allowed_handler() -> Response:
            if self.app._cors_enabled and method == "OPTIONS":
                return self._preflight_response(allowed_methods | {"OPTIONS"})

            custom_response = self._custom_response(MethodNotAllowedError)
            if custom_response is not None:
                return custom_response

            return self._method_not_allowed_response(allowed_methods)

        return self._call_synthetic_route(method=method, path=path, handler=method_not_allowed_handler)

    def _call_synthetic_route(self, method: str, path: str, handler: Callable[[], Response]) -> Response:
        route = Route(
            method=method,
            path=path,
            pattern=self.app._router.compile_regex(r"^.*$"),
            handler=handler,
            cors=self.app._cors_enabled,
        )
        self.app.append_context(_route=route, _path=path)
        return self.app._call_route(route, route_arguments={})

    def _preflight_response(self, allowed_methods: set[str]) -> Response:
        return Response(
            status_code=HTTPStatus.NO_CONTENT.value,
            content_type=None,
            headers={"Access-Control-Allow-Methods": CORSConfig.build_allow_methods(allowed_methods)},
            body="",
        )

    def _custom_response(self, exc_class: type[Exception]) -> Response | None:
        handler = self.app._router.exception_handler_manager.lookup_exception_handler(exc_class)
        if handler is None:
            return None
        return handler(exc_class())

    def _not_found_response(self) -> Response:
        return Response(
            status_code=HTTPStatus.NOT_FOUND.value,
            content_type=content_types.APPLICATION_JSON,
            body={"statusCode": HTTPStatus.NOT_FOUND.value, "message": "Not Found"},
        )

    def _method_not_allowed_response(self, allowed_methods: set[str]) -> Response:
        return Response(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED.value,
            content_type=content_types.APPLICATION_JSON,
            headers={"Allow": CORSConfig.build_allow_methods(allowed_methods)},
            body={
                "statusCode": HTTPStatus.METHOD_NOT_ALLOWED.value,
                "message": "Method Not Allowed",
            },
        )


__all__ = ["RoutingFallbackHandler"]
