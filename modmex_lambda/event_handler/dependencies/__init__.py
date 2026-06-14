from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modmex_lambda.dependencies import DefaultDependencyResolver, DependencyResolver, InjectorDependencyResolver
    from modmex_lambda.event_handler.dependencies.depends import Depends

_EXPORTS = {
    "DefaultDependencyResolver": ("modmex_lambda.dependencies", "DefaultDependencyResolver"),
    "DependencyResolver": ("modmex_lambda.dependencies", "DependencyResolver"),
    "Depends": ("modmex_lambda.event_handler.dependencies.depends", "Depends"),
    "InjectorDependencyResolver": ("modmex_lambda.dependencies", "InjectorDependencyResolver"),
}

__all__ = [
    "DefaultDependencyResolver",
    "DependencyResolver",
    "Depends",
    "InjectorDependencyResolver",
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
