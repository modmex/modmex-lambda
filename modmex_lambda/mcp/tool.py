"""MCP tool registration and invocation."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any, Callable, get_type_hints

from modmex import BaseModel
from modmex_lambda.event_handler.dependencies.dependant import get_dependant
from modmex_lambda.event_handler.dependencies.depends import Depends, solve_dependencies
from modmex_lambda.event_handler.routing import capture_definition_locals
from modmex_lambda.validation import ModmexValidator
from modmex_lambda.mcp.middleware import MCPContext, MCPMiddleware, run_middleware, run_middleware_async
from modmex_lambda.mcp.schema import input_schema


class MCPTool:
    def __init__(
        self,
        handler: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        middlewares: list[MCPMiddleware] | None = None,
    ) -> None:
        self.handler = handler
        self.name = name or handler.__name__
        self.description = description or inspect.getdoc(handler) or ""
        capture_definition_locals(handler)
        self.dependant = get_dependant(path="", call=handler, responses=None)
        try:
            self._hints = get_type_hints(handler, include_extras=True)
        except (NameError, TypeError):
            self._hints = getattr(handler, "__annotations__", {}).copy()
        self.middlewares = list(middlewares or [])

    def add_middlewares(self, middlewares: list[MCPMiddleware]) -> None:
        self.middlewares = [*middlewares, *self.middlewares]

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": input_schema(self.handler),
        }

    def argument_names(self) -> set[str]:
        hints = self._hints
        names: set[str] = set()
        for name, parameter in inspect.signature(self.handler).parameters.items():
            annotation = hints.get(name, parameter.annotation)
            if name not in {"self", "request", "context", "ctx"} and not _has_depends(annotation):
                names.add(name)
        return names

    def invoke(
        self,
        arguments: dict[str, Any] | None = None,
        *,
        request: Any = None,
        dependency_overrides: dict[Callable[..., Any], Callable[..., Any]] | None = None,
        dependency_resolver: Any = None,
        middleware_context: MCPContext | None = None,
        middlewares: list[MCPMiddleware] | None = None,
    ) -> Any:
        arguments = arguments or {}
        unknown = set(arguments) - self.argument_names()
        if unknown:
            raise ValueError(f"Unexpected tool arguments: {', '.join(sorted(unknown))}")
        parameters = inspect.signature(self.handler).parameters
        for name in self.argument_names():
            parameter = parameters[name]
            if name not in arguments:
                if parameter.default is inspect.Signature.empty:
                    raise ValueError(f"Missing tool argument: {name}")
                continue
            try:
                _reject_extra_model_fields(arguments[name], self._hints.get(name, parameter.annotation), [name])
                arguments[name] = ModmexValidator().validate(
                    arguments[name],
                    self._hints.get(name, parameter.annotation),
                    [name],
                )
            except Exception as exc:
                raise ValueError(f"Invalid tool argument '{name}': {exc}") from exc
        def endpoint(ctx: MCPContext) -> Any:
            values = solve_dependencies(
                dependant=self.dependant,
                request=request,
                dependency_overrides=dependency_overrides,
                dependency_resolver=dependency_resolver,
            )
            if "request" in parameters and "request" not in values:
                values["request"] = request
            for name in ("context", "ctx"):
                if name in parameters and name not in values:
                    values[name] = ctx
            values.update(arguments)
            return self.handler(**values)

        context = middleware_context or MCPContext(request=request, server=None, capability="tools", name=self.name, arguments=arguments)
        return run_middleware([*(middlewares or []), *self.middlewares], context, endpoint)

    async def ainvoke(self, arguments: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        arguments = arguments or {}
        middleware_context = kwargs.pop("middleware_context", None)
        middlewares = kwargs.pop("middlewares", None)
        request = kwargs.get("request")
        unknown = set(arguments) - self.argument_names()
        if unknown:
            raise ValueError(f"Unexpected tool arguments: {', '.join(sorted(unknown))}")
        parameters = inspect.signature(self.handler).parameters
        for name in self.argument_names():
            parameter = parameters[name]
            if name not in arguments:
                if parameter.default is inspect.Signature.empty:
                    raise ValueError(f"Missing tool argument: {name}")
                continue
            _reject_extra_model_fields(arguments[name], self._hints.get(name, parameter.annotation), [name])
            arguments[name] = ModmexValidator().validate(arguments[name], self._hints.get(name, parameter.annotation), [name])

        def endpoint(ctx: MCPContext) -> Any:
            values = solve_dependencies(dependant=self.dependant, request=request, dependency_overrides=kwargs.get("dependency_overrides"), dependency_resolver=kwargs.get("dependency_resolver"))
            if "request" in parameters and "request" not in values:
                values["request"] = request
            for name in ("context", "ctx"):
                if name in parameters and name not in values:
                    values[name] = ctx
            values.update(arguments)
            return self.handler(**values)

        context = middleware_context or MCPContext(request=request, server=None, capability="tools", name=self.name, arguments=arguments)
        return await run_middleware_async([*(middlewares or []), *self.middlewares], context, endpoint)

    def arguments(self) -> set[str]:
        """Compatibility alias for :meth:`argument_names`."""
        return self.argument_names()


def _has_depends(annotation: Any) -> bool:
    from typing import Annotated, get_args, get_origin

    return get_origin(annotation) is Annotated and any(
        isinstance(item, Depends) for item in get_args(annotation)[1:]
    )


def _reject_extra_model_fields(value: Any, annotation: Any, path: list[str]) -> None:
    """Keep MCP input strict even though BaseModel accepts extra constructor fields."""
    from typing import Annotated, Union, get_args, get_origin
    import types

    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        for candidate in get_args(annotation):
            if candidate is type(None):
                continue
            try:
                _reject_extra_model_fields(value, candidate, path)
                return
            except ValueError:
                continue
        return
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        if not isinstance(value, Mapping):
            return
        fields = set(getattr(annotation, "__annotations__", {}))
        unknown = set(value) - fields
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"Error at {'.'.join(path)}: unexpected field(s): {names}")
