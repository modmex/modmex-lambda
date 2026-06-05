"""Dependency injection primitives for event handler resolvers."""

from __future__ import annotations

from typing import Annotated, Any, Callable, get_args, get_origin, get_type_hints

from modmex_lambda.event_handler.dependencies.compat import ModelField
from modmex_lambda.event_handler.dependencies.types import CacheKey
from modmex_lambda.event_handler.request import Request


class Dependant:
    """Route callable metadata used by dependency parsing and request validation."""

    def __init__(
        self,
        *,
        path_params: list[ModelField] | None = None,
        query_params: list[ModelField] | None = None,
        header_params: list[ModelField] | None = None,
        cookie_params: list[ModelField] | None = None,
        body_params: list[ModelField] | None = None,
        return_param: ModelField | None = None,
        name: str | None = None,
        call: Callable[..., Any] | None = None,
        dependencies: list[DependencyParam] | None = None,
        path: str | None = None,
    ) -> None:
        self.path_params = path_params or []
        self.query_params = query_params or []
        self.header_params = header_params or []
        self.cookie_params = cookie_params or []
        self.body_params = body_params or []
        self.return_param = return_param
        self.dependencies = dependencies or []
        self.name = name
        self.call = call
        self.path = path
        self.cache_key: CacheKey = call


class DependencyResolutionError(Exception):
    """Raised when a dependency cannot be resolved."""


class Depends:
    def __init__(self, dependency: Callable[..., Any], *, use_cache: bool = True) -> None:
        if not callable(dependency):
            raise DependencyResolutionError(
                f"Depends() requires a callable, got {type(dependency).__name__}: {dependency!r}",
            )
        self.dependency = dependency
        self.use_cache = use_cache


class _DependencyNode:
    """Lightweight node in a dependency tree."""

    def __init__(self, *, param_name: str, depends: Depends, sub_tree: DependencyTree) -> None:
        self.param_name = param_name
        self.depends = depends
        self.dependant = sub_tree


class DependencyTree:
    """Lightweight dependency tree for call-time dependency resolution."""

    def __init__(self, *, dependencies: list[_DependencyNode] | None = None) -> None:
        self.dependencies = dependencies or []


class DependencyParam:
    """Dependency metadata attached to a route parameter."""

    def __init__(self, *, param_name: str, depends: Depends, dependant: Dependant) -> None:
        self.param_name = param_name
        self.depends = depends
        self.dependant = dependant


def _get_depends_from_annotation(annotation: Any) -> Depends | None:
    if get_origin(annotation) is Annotated:
        for arg in get_args(annotation)[1:]:
            if isinstance(arg, Depends):
                return arg
    return None


def build_dependency_tree(func: Callable[..., Any]) -> DependencyTree:
    """Build a dependency tree from Annotated parameters."""
    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception:
        return DependencyTree()

    dependencies: list[_DependencyNode] = []
    for param_name, annotation in hints.items():
        if param_name == "return":
            continue

        depends = _get_depends_from_annotation(annotation)
        if depends is None:
            continue

        dependencies.append(
            _DependencyNode(
                param_name=param_name,
                depends=depends,
                sub_tree=build_dependency_tree(depends.dependency),
            ),
        )

    return DependencyTree(dependencies=dependencies)


def solve_dependencies(
    *,
    dependant: Dependant | DependencyTree,
    request: Request | None = None,
    dependency_overrides: dict[Callable[..., Any], Callable[..., Any]] | None = None,
    dependency_cache: dict[Callable[..., Any], Any] | None = None,
) -> dict[str, Any]:
    """Resolve all Depends parameters for a route or lightweight dependency tree."""
    from modmex_lambda.event_handler.request import Request as RequestClass

    cache = dependency_cache if dependency_cache is not None else {}
    overrides = dependency_overrides or {}
    values: dict[str, Any] = {}

    for dep in dependant.dependencies:
        dependency = overrides.get(dep.depends.dependency, dep.depends.dependency)

        if dep.depends.use_cache and dependency in cache:
            values[dep.param_name] = cache[dependency]
            continue

        sub_values = solve_dependencies(
            dependant=dep.dependant,
            request=request,
            dependency_overrides=overrides,
            dependency_cache=cache,
        )
        sub_values.update(_request_injection_values(dependency, request, RequestClass))

        try:
            solved = dependency(**sub_values)
        except Exception as exc:
            dep_name = getattr(dependency, "__name__", repr(dependency))
            raise DependencyResolutionError(
                f"Failed to resolve dependency '{dep_name}' for parameter '{dep.param_name}': {exc}",
            ) from exc

        if dep.depends.use_cache:
            cache[dependency] = solved

        values[dep.param_name] = solved

    return values


def _request_injection_values(
    dependency: Callable[..., Any],
    request: Request | None,
    request_class: type[Request],
) -> dict[str, Request]:
    if request is None:
        return {}

    try:
        hints = get_type_hints(dependency)
    except Exception:
        return {}

    return {name: request for name, annotation in hints.items() if annotation is request_class}


__all__ = [
    "Dependant",
    "DependencyParam",
    "Depends",
    "_get_depends_from_annotation",
    "build_dependency_tree",
    "solve_dependencies",
]
