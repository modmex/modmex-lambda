"""Public API for modmex-lambda."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .event_handler import (
        ApiGatewayHttpResolver,
        ApiGatewayRestResolver,
        Response,
    )
    from .event_handler.request import Request
    from .event_sources import event_source
    from .event_handler.dependencies.depends import (
        DefaultDependencyResolver,
        DependencyResolver,
        Depends,
        InjectorDependencyResolver,
    )
    from .logging import Logger
    from .parser import event_parser, parse
    from .validation import ModmexValidator, ValidationError

_EXPORTS = {
    "ApiGatewayHttpResolver": ("modmex_lambda.event_handler", "ApiGatewayHttpResolver"),
    "ApiGatewayRestResolver": ("modmex_lambda.event_handler", "ApiGatewayRestResolver"),
    "Request": ("modmex_lambda.event_handler.request", "Request"),
    "Response": ("modmex_lambda.event_handler", "Response"),
    "parse": ("modmex_lambda.parser", "parse"),
    "event_parser": ("modmex_lambda.parser", "event_parser"),
    "event_source": ("modmex_lambda.event_sources", "event_source"),
    "DefaultDependencyResolver": ("modmex_lambda.event_handler.dependencies.depends", "DefaultDependencyResolver"),
    "DependencyResolver": ("modmex_lambda.event_handler.dependencies.depends", "DependencyResolver"),
    "Depends": ("modmex_lambda.event_handler.dependencies.depends", "Depends"),
    "InjectorDependencyResolver": ("modmex_lambda.event_handler.dependencies.depends", "InjectorDependencyResolver"),
    "Logger": ("modmex_lambda.logging", "Logger"),
    "ModmexValidator": ("modmex_lambda.validation", "ModmexValidator"),
    "ValidationError": ("modmex_lambda.validation", "ValidationError"),
}

__all__ = [
    "ApiGatewayHttpResolver",
    "ApiGatewayRestResolver",
    "Request",
    "Response",
    "parse",
    "event_parser",
    "event_source",
    "DefaultDependencyResolver",
    "DependencyResolver",
    "Depends",
    "InjectorDependencyResolver",
    "Logger",
    "ModmexValidator",
    "ValidationError",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr = target
    value = getattr(import_module(module_name), attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals().keys(), *__all__])
