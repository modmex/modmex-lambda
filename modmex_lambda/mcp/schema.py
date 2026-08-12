"""Provider-neutral input schemas for MCP operations."""

from __future__ import annotations

import inspect
import types
from collections.abc import Sequence
from copy import deepcopy
from enum import Enum
from typing import Annotated, Any, Literal, Union, get_args, get_origin, get_type_hints

from modmex import BaseModel


def input_schema(
    callable_: Any,
    *,
    excluded: set[str] | None = None,
) -> dict[str, Any]:
    """Build an object schema from a callable signature.

    Dependency-injected parameters are excluded from the public MCP input.
    """
    excluded = excluded or set()
    try:
        hints = get_type_hints(callable_, include_extras=True)
    except Exception:
        hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, parameter in inspect.signature(callable_).parameters.items():
        if name in excluded or name in {"self", "request", "context", "ctx"}:
            continue
        annotation = hints.get(name, parameter.annotation)
        if _is_dependency(annotation):
            continue
        properties[name] = schema_for_type(annotation)
        if parameter.default is inspect.Signature.empty:
            required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def schema_for_type(annotation: Any) -> dict[str, Any]:
    if annotation is inspect.Signature.empty or annotation is Any:
        return {}
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (Union, types.UnionType):
        non_none = [arg for arg in args if arg is not type(None)]
        if len(non_none) == 1 and len(non_none) != len(args):
            return {"anyOf": [schema_for_type(non_none[0]), {"type": "null"}]}
        return {"anyOf": [schema_for_type(arg) for arg in args]}
    if origin in (list, Sequence):
        return {"type": "array", "items": schema_for_type(args[0] if args else Any)}
    if origin is dict:
        return {"type": "object"}
    if origin is Literal:
        values = list(args)
        return {"enum": values, "type": _json_type(type(values[0])) if values else "string"}
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        values = [item.value for item in annotation]
        return {"enum": values, "type": _json_type(type(values[0])) if values else "string"}
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return deepcopy(annotation.model_json_schema())
    return {"type": _json_type(annotation)}


def _is_dependency(annotation: Any) -> bool:
    from modmex_lambda.event_handler.dependencies.depends import Depends

    if get_origin(annotation) is not Annotated:
        return False
    return any(isinstance(item, Depends) for item in get_args(annotation)[1:])


def _accepts_none(annotation: Any) -> bool:
    origin = get_origin(annotation)
    return origin in (Union, types.UnionType) and any(arg is type(None) for arg in get_args(annotation))


def _json_type(annotation: Any) -> str:
    return {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }.get(annotation, "string")
