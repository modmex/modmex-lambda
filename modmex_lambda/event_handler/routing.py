"""Routing primitives for API Gateway resolvers."""

from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Pattern

from modmex_lambda.event_handler.constants import DEFAULT_STATUS_CODE
from modmex_lambda.event_handler.dependencies.dependant import get_dependant, is_request_annotation
from modmex_lambda.event_handler.dependencies.depends import solve_dependencies
from modmex_lambda.event_handler.dependencies.params import Dependant
from modmex_lambda.event_handler.response import Response
from modmex_lambda.event_handler.types import IApiGatewayResolver
from modmex_lambda.shared.types import AnyCallableT


Handler = AnyCallableT
NextMiddleware = Callable[..., dict | tuple | Response]

_DYNAMIC_ROUTE_PATTERN = r"(<\w+>)"
_SAFE_URI = "-._~()'!*:@,;=+&$"  # https://www.ietf.org/rfc/rfc3986.txt
_UNSAFE_URI = r"%<> \[\]{}|^"
_NAMED_GROUP_BOUNDARY_PATTERN = rf"(?P\1[{_SAFE_URI}{_UNSAFE_URI}\\w]+)"
_ROUTE_REGEX = "^{}$"


class IRoute(ABC):
    method: str
    path: str

    @abstractmethod
    def invoke(
        self,
        router_middlewares: list[Callable],
        app: IApiGatewayResolver,
        route_arguments: dict[str, str],
    ) -> Response:
        raise NotImplementedError

    @abstractmethod
    def match(self, path: str) -> dict[str, str] | None:
        raise NotImplementedError

    @property
    @abstractmethod
    def dependant(self) -> Dependant:
        raise NotImplementedError()


class HasRoutes(ABC):
    @abstractmethod
    def route(
        self,
        rule: str,
        method: str | list[str] | tuple[str],
        description: str | None = None,
        status_code: int = DEFAULT_STATUS_CODE,
        middlewares: list[AnyCallableT] | None = None,
        cors: bool | None = None,
        compress: bool = False,
        cache_control: str | None = None,
    ):
        raise NotImplementedError

    def get(
        self,
        rule: str,
        description: str | None = None,
        status_code: int = DEFAULT_STATUS_CODE,
        middlewares: list[AnyCallableT] | None = None,
        cors: bool | None = None,
        compress: bool = False,
        cache_control: str | None = None,
    ) -> Callable[[AnyCallableT], AnyCallableT]:
        return self.route(
            rule=rule,
            method="GET",
            description=description,
            status_code=status_code,
            middlewares=middlewares,
            cors=cors,
            compress=compress,
            cache_control=cache_control,
        )

    def post(
        self,
        rule: str,
        description: str | None = None,
        status_code: int = DEFAULT_STATUS_CODE,
        middlewares: list[AnyCallableT] | None = None,
        cors: bool | None = None,
        compress: bool = False,
        cache_control: str | None = None,
    ) -> Callable[[AnyCallableT], AnyCallableT]:
        return self.route(
            rule=rule,
            method="POST",
            description=description,
            status_code=status_code,
            middlewares=middlewares,
            cors=cors,
            compress=compress,
            cache_control=cache_control,
        )

    def put(
        self,
        rule: str,
        description: str | None = None,
        status_code: int = DEFAULT_STATUS_CODE,
        middlewares: list[AnyCallableT] | None = None,
        cors: bool | None = None,
        compress: bool = False,
        cache_control: str | None = None,
    ) -> Callable[[AnyCallableT], AnyCallableT]:
        return self.route(
            rule=rule,
            method="PUT",
            description=description,
            status_code=status_code,
            middlewares=middlewares,
            cors=cors,
            compress=compress,
            cache_control=cache_control,
        )

    def patch(
        self,
        rule: str,
        description: str | None = None,
        status_code: int = DEFAULT_STATUS_CODE,
        middlewares: list[AnyCallableT] | None = None,
        cors: bool | None = None,
        compress: bool = False,
        cache_control: str | None = None,
    ) -> Callable[[AnyCallableT], AnyCallableT]:
        return self.route(
            rule=rule,
            method="PATCH",
            description=description,
            status_code=status_code,
            middlewares=middlewares,
            cors=cors,
            compress=compress,
            cache_control=cache_control,
        )

    def delete(
        self,
        rule: str,
        description: str | None = None,
        status_code: int = DEFAULT_STATUS_CODE,
        middlewares: list[AnyCallableT] | None = None,
        cors: bool | None = None,
        compress: bool = False,
        cache_control: str | None = None,
    ) -> Callable[[AnyCallableT], AnyCallableT]:
        return self.route(
            rule=rule,
            method="DELETE",
            description=description,
            status_code=status_code,
            middlewares=middlewares,
            cors=cors,
            compress=compress,
            cache_control=cache_control,
        )

    def header(
        self,
        rule: str,
        description: str | None = None,
        status_code: int = DEFAULT_STATUS_CODE,
        middlewares: list[AnyCallableT] | None = None,
        cors: bool | None = None,
        compress: bool = False,
        cache_control: str | None = None,
    ) -> Callable[[AnyCallableT], AnyCallableT]:
        return self.route(
            rule=rule,
            method="HEAD",
            description=description,
            status_code=status_code,
            middlewares=middlewares,
            cors=cors,
            compress=compress,
            cache_control=cache_control,
        )


class IRouter(ABC):
    _routes: list[IRoute]

    @abstractmethod
    def include_router(self, router: IRouter, prefix: str = "") -> None:
        raise NotImplementedError


class MiddlewareChainLink:
    def __init__(
        self,
        current_middleware: Callable[..., Any],
        next_middleware: Callable[..., Any],
    ) -> None:
        self.current_middleware = current_middleware
        self.next_middleware = next_middleware
        self._next_middleware_name = callable_name(next_middleware)

    @property
    def __name__(self) -> str:
        return callable_name(self.current_middleware)

    def __str__(self) -> str:
        return f"{self.__name__} -> {self._next_middleware_name}"

    def __call__(self, app: IApiGatewayResolver) -> dict | tuple | Response:
        return self.current_middleware(app, self.next_middleware)


def callable_name(value: Callable[..., Any]) -> str:
    return getattr(value, "__name__", value.__class__.__name__)


class Route(IRoute):
    __slots__ = (
        "method",
        "path",
        "handler",
        "pattern",
        "description",
        "status_code",
        "middlewares",
        "_middleware_stack",
        "_middleware_stack_built",
        "cors",
        "cache_control",
        "compress",
    )

    def __init__(
        self,
        method: str,
        path: str,
        handler: Callable,
        cors: bool,
        pattern: Pattern,
        description: str | None = None,
        status_code: int | None = DEFAULT_STATUS_CODE,
        middlewares: list[AnyCallableT] | None = None,
        compress: bool = False,
        cache_control: str | None = None,
    ) -> None:
        self.method = method
        self.path = path
        self.handler = handler
        self.cors = cors if cors is not None else False
        self._middleware_stack = handler
        self.pattern = pattern
        self.middlewares = middlewares or []
        self._middleware_stack_built = False
        self.description = description
        self.status_code = status_code
        self._dependant: Dependant | None = None
        self.responses: dict[int, Any] | None = None
        self.compress = compress
        self.cache_control = cache_control
        self.request_param_name: str | None = None
        self.request_param_name_checked = False

    @property
    def dependant(self) -> Dependant:
        if not self._dependant:
            self._dependant = get_dependant(path=self.path, call=self.handler, responses=self.responses)
        return self._dependant

    @property
    def has_dependencies(self) -> bool:
        return bool(self.dependant.dependencies)

    def invoke(
        self,
        router_middlewares: list[Callable],
        app: IApiGatewayResolver,
        route_arguments: dict[str, str],
    ) -> Response:
        if not self._middleware_stack_built:
            self._build_middleware_stack(router_middlewares=router_middlewares, app=app)

        app.append_context(_route_args=route_arguments)
        return self._middleware_stack(app)

    def match(self, path: str) -> dict[str, str] | None:
        match = self.pattern.match(path)
        if match is None:
            return None
        if isinstance(match, dict):
            return match
        return match.groupdict()

    def _build_middleware_stack(self, router_middlewares: list[Callable[..., Any]], app: IApiGatewayResolver) -> None:
        middlewares = [
            app._dependency_middleware,
            *router_middlewares,
            *self.middlewares,
            RouteEndpointInvoker(),
        ]

        for handler in reversed(middlewares):
            self._middleware_stack = MiddlewareChainLink(
                current_middleware=handler,
                next_middleware=self._middleware_stack,
            )

        self._middleware_stack_built = True


class Router(IRouter):
    __slots__ = (
        "_routes",
        "_routes_with_middlewares",
        "context",
        "_dynamic_routes",
        "_static_routes",
        "_path_methods",
        "cors_methods",
        "exception_handler_manager",
    )

    def __init__(self):
        from modmex_lambda.event_handler.exception_handler import ExceptionHandlerManager

        self._routes: list[Route] = []
        self._routes_with_middlewares: dict[tuple, list[Callable]] = {}
        self.context = {}
        self._dynamic_routes: list[Route] = []
        self._static_routes: dict[tuple[str, str], Route] = {}
        self._path_methods: dict[str, set[str]] = {}
        self.cors_methods: set[str] = set()
        self.exception_handler_manager = ExceptionHandlerManager()

    def route(
        self,
        rule: str,
        method: str | list[str] | tuple[str],
        description: str | None = None,
        status_code: int = DEFAULT_STATUS_CODE,
        middlewares: list[AnyCallableT] | None = None,
        cors: bool | None = None,
        compress: bool = False,
        cache_control: str | None = None,
    ) -> Callable[[AnyCallableT], AnyCallableT]:
        def decorator(func: AnyCallableT) -> AnyCallableT:
            capture_definition_locals(func)
            methods = (method,) if isinstance(method, str) else method
            for item in methods:
                self._add_route(
                    rule=rule,
                    method=item,
                    handler=func,
                    description=description,
                    status_code=status_code,
                    middlewares=middlewares,
                    cors=cors,
                    compress=compress,
                    cache_control=cache_control,
                )
            return func

        return decorator

    def _add_route(
        self,
        rule: str,
        method: str,
        handler: AnyCallableT,
        description: str | None = None,
        status_code: int | None = DEFAULT_STATUS_CODE,
        middlewares: list[AnyCallableT] | None = None,
        cors: bool | None = None,
        compress: bool = False,
        cache_control: str | None = None,
    ) -> None:
        method = method.upper()
        route = Route(
            method=method,
            path=rule,
            handler=handler,
            pattern=self.compile_regex(rule),
            description=description,
            status_code=status_code,
            middlewares=middlewares,
            cors=cors,
            compress=compress,
            cache_control=cache_control,
        )
        self._routes.append(route)
        self._path_methods.setdefault(rule, set()).add(method)

        if route.pattern.groups > 0:
            self._dynamic_routes.append(route)
        else:
            self._static_routes[(method, rule)] = route

        self.cors_methods.add(method)

    def include_router(self, router: Router, prefix: str = "") -> None:
        for route in router._routes:
            self._add_route(
                rule=prefix + route.path,
                method=route.method,
                handler=route.handler,
                description=route.description,
                status_code=route.status_code,
                middlewares=route.middlewares,
                cors=route.cors,
                compress=route.compress,
                cache_control=route.cache_control,
            )

    def exception_handler(self, exc_class: type[Exception] | list[type[Exception]]):
        return self.exception_handler_manager.exception_handler(exc_class)

    def match(self, method: str, path: str) -> tuple[Route | None, dict[str, str], set[str]]:
        method = method.upper()
        route = self._static_routes.get((method, path)) or self._static_routes.get(("ANY", path))
        if route is not None:
            return route, {}, set()

        allowed_methods = set(self._path_methods.get(path, set()))

        for route in self._dynamic_routes:
            path_params = route.match(path)
            if path_params is None:
                continue
            allowed_methods.add(route.method.upper())
            if route.method.upper() in {method, "ANY"}:
                return route, path_params, set()
        return None, {}, allowed_methods

    @staticmethod
    def compile_regex(rule: str, base_regex: str = _ROUTE_REGEX):
        rule_regex = re.sub(_DYNAMIC_ROUTE_PATTERN, _NAMED_GROUP_BOUNDARY_PATTERN, rule)
        return re.compile(base_regex.format(rule_regex))


def capture_definition_locals(func: Callable[..., Any]) -> None:
    frame = inspect.currentframe()
    if frame is not None and frame.f_back is not None and frame.f_back.f_back is not None:
        setattr(func, "__modmex_lambda_localns__", dict(frame.f_back.f_back.f_locals))


def _find_request_param_name(func: Callable) -> str | None:
    from typing import get_type_hints

    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    for param_name, annotation in hints.items():
        if is_request_annotation(annotation):
            return param_name

    return None


class RouteEndpointInvoker:
    def __call__(self, app: IApiGatewayResolver, next_middleware: NextMiddleware) -> Response:
        return self.handler(app, next_middleware)

    def handler(self, app: IApiGatewayResolver, next_middleware: NextMiddleware) -> Response:
        route_args: dict = app.context.get("_route_args", {})
        route: Route | None = app.context.get("_route")

        if route is not None:
            if not route.request_param_name_checked:
                route.request_param_name = _find_request_param_name(next_middleware)
                route.request_param_name_checked = True

            if route.request_param_name:
                route_args = {
                    **route_args,
                    route.request_param_name: app.request,
                }

            if route.has_dependencies:
                route_args.update(
                    solve_dependencies(
                        dependant=route.dependant,
                        request=app.request,
                        dependency_overrides=app.dependency_overrides or None,
                    ),
                )

        return app._to_response(next_middleware(**route_args))


__all__ = [
    "HasRoutes",
    "IRoute",
    "IRouter",
    "Route",
    "Router",
]
