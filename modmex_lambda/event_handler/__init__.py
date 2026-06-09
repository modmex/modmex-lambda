from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import content_types
    from .api_gateway import (
        ApiGatewayHttpResolver,
        ApiGatewayRestResolver,
        Response,
    )
    from .dependencies.depends import DefaultDependencyResolver, DependencyResolver, Depends, InjectorDependencyResolver

_EXPORTS = {
    "ApiGatewayHttpResolver": ("modmex_lambda.event_handler.api_gateway", "ApiGatewayHttpResolver"),
    "ApiGatewayRestResolver": ("modmex_lambda.event_handler.api_gateway", "ApiGatewayRestResolver"),
    "Response": ("modmex_lambda.event_handler.api_gateway", "Response"),
    "DefaultDependencyResolver": ("modmex_lambda.event_handler.dependencies.depends", "DefaultDependencyResolver"),
    "DependencyResolver": ("modmex_lambda.event_handler.dependencies.depends", "DependencyResolver"),
    "Depends": ("modmex_lambda.event_handler.dependencies.depends", "Depends"),
    "InjectorDependencyResolver": ("modmex_lambda.event_handler.dependencies.depends", "InjectorDependencyResolver"),
    "content_types": ("modmex_lambda.event_handler.content_types", None),
}

__all__ = [
    "ApiGatewayHttpResolver",
    "ApiGatewayRestResolver",
    "Response",
    "DefaultDependencyResolver",
    "DependencyResolver",
    "Depends",
    "InjectorDependencyResolver",
    "content_types",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr = target
    module = import_module(module_name)
    value = module if attr is None else getattr(module, attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals().keys(), *__all__])
