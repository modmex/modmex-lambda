"""Shared dependency resolver primitives for REST and stream handlers."""

from __future__ import annotations

import inspect
from importlib import import_module
from typing import TYPE_CHECKING, Any, Callable, Protocol

if TYPE_CHECKING:
    from modmex_lambda.connectors import AwsConnectorsModule


class DependencyResolver(Protocol):
    """Resolves a dependency token into the value passed to a handler."""

    def resolve(
        self,
        dependency: Callable[..., Any] | type[Any],
        *,
        values: dict[str, Any] | None = None,
    ) -> Any:
        ...


class DefaultDependencyResolver:
    """Default resolver that calls dependency functions with solved values."""

    def resolve(
        self,
        dependency: Callable[..., Any] | type[Any],
        *,
        values: dict[str, Any] | None = None,
    ) -> Any:
        return dependency(**(values or {}))


class InjectorDependencyResolver:
    """Adapter for the ``injector`` package."""

    def __init__(self, injector: Any) -> None:
        self.injector = injector

    def resolve(
        self,
        dependency: Callable[..., Any] | type[Any],
        *,
        values: dict[str, Any] | None = None,
    ) -> Any:
        kwargs = values or {}

        if hasattr(self.injector, "call_with_injection") and not inspect.isclass(dependency):
            return self.injector.call_with_injection(dependency, kwargs=kwargs)

        if not kwargs and inspect.isclass(dependency) and hasattr(self.injector, "get"):
            return self.injector.get(dependency)

        return dependency(**kwargs)


_default_dependency_resolver: DependencyResolver | None = None

_LAZY_EXPORTS = {
    "AwsConnectorsModule": ("modmex_lambda.connectors", "AwsConnectorsModule"),
}


def create_dependency_resolver(*modules: Any) -> InjectorDependencyResolver:
    from injector import Injector
    from modmex_lambda.connectors import AwsConnectorsModule

    return InjectorDependencyResolver(
        Injector([AwsConnectorsModule(), *modules])
    )


def default_dependency_resolver() -> DependencyResolver:
    global _default_dependency_resolver

    if _default_dependency_resolver is None:
        _default_dependency_resolver = create_dependency_resolver()
    return _default_dependency_resolver


__all__ = [
    "AwsConnectorsModule",
    "DefaultDependencyResolver",
    "DependencyResolver",
    "InjectorDependencyResolver",
    "create_dependency_resolver",
    "default_dependency_resolver",
]


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr = target
    value = getattr(import_module(module_name), attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals().keys(), *__all__])
