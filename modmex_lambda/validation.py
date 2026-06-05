"""Validation adapter layer backed by Modmex."""

from __future__ import annotations

import inspect
import json
import types
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal, Protocol, Union, get_args, get_origin

from modmex import BaseModel
from modmex.errors import ValidationError
from modmex.validation import (
    bool_validator,
    decimal_validator,
    float_validator,
    int_validator,
    parse_date,
    parse_datetime,
    str_validator,
)


class Validator(Protocol):
    def validate(self, value: Any, target_type: Any, loc: list[Any] | None = None) -> Any:
        """Validate/coerce ``value`` into ``target_type``."""

    def serialize(self, value: Any) -> Any:
        """Serialize a model-like value into Python primitives."""

    def dumps(self, value: Any) -> str:
        """Serialize a value to JSON."""


class ModmexValidator:
    def __init__(self) -> None:
        self._primitive_validators = {
            str: str_validator,
            int: int_validator,
            bool: bool_validator,
            float: float_validator,
            datetime: parse_datetime,
            date: parse_date,
            Decimal: decimal_validator,
        }

    def validate(self, value: Any, target_type: Any, loc: list[Any] | None = None) -> Any:
        return self._validate_value(target_type, value, list(loc or []))

    def serialize(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return value

    def dumps(self, value: Any) -> str:
        if hasattr(value, "model_dump_json"):
            return value.model_dump_json()
        return json.dumps(self.serialize(value), separators=(",", ":"), default=self.serialize)

    def _validate_value(self, annotation: Any, value: Any, loc: list[Any]) -> Any:
        if annotation is inspect.Signature.empty or annotation is Any:
            return value

        if value is None:
            if self._accepts_none(annotation):
                return None
            raise ValidationError(errors=[{"loc": loc, "msg": "Field required", "type": "missing"}])

        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is not None:
            if origin is Annotated:
                return self._validate_value(args[0], value, loc)

            if origin in (list, Sequence):
                item_type = args[0] if args else Any
                return [self._validate_value(item_type, item, loc + [idx]) for idx, item in enumerate(value)]

            if origin is tuple:
                return self._validate_tuple(args, value, loc)

            if origin is dict:
                return self._validate_dict(args, value, loc)

            if origin in (Union, types.UnionType):
                return self._validate_union(args, value, loc)

        if self._is_literal(annotation):
            return self._validate_literal(annotation, value, loc)

        return self._validate_leaf(annotation, value, loc)

    def _validate_tuple(self, args: tuple[Any, ...], value: Any, loc: list[Any]) -> tuple[Any, ...]:
        if not isinstance(value, tuple):
            raise ValidationError(errors=[{"loc": loc, "msg": "must be a tuple", "type": "type_error.tuple"}])
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(self._validate_value(args[0], item, loc + [idx]) for idx, item in enumerate(value))
        if len(value) != len(args):
            raise ValidationError(errors=[{"loc": loc, "msg": "Tuple length mismatch", "type": "type_error"}])
        return tuple(self._validate_value(arg, item, loc + [idx]) for idx, (arg, item) in enumerate(zip(args, value)))

    def _validate_dict(self, args: tuple[Any, ...], value: Any, loc: list[Any]) -> dict[Any, Any]:
        if not isinstance(value, Mapping):
            raise ValidationError(errors=[{"loc": loc, "msg": "must be a dict", "type": "type_error.dict"}])
        key_type, value_type = args if args else (Any, Any)
        validated: dict[Any, Any] = {}
        for key, item in value.items():
            valid_key = self._validate_value(key_type, key, loc + ["<key>"])
            validated[valid_key] = self._validate_value(value_type, item, loc + [key])
        return validated

    def _validate_union(self, args: tuple[Any, ...], value: Any, loc: list[Any]) -> Any:
        candidate_errors: list[dict[str, Any]] = []
        for candidate in args:
            try:
                return self._validate_value(candidate, value, loc)
            except ValidationError as exc:
                candidate_errors.extend(exc.errors)
        raise ValidationError(
            errors=candidate_errors or [{"loc": loc, "msg": "Invalid union type", "type": "type_error"}]
        )

    def _validate_literal(self, annotation: Any, value: Any, loc: list[Any]) -> Any:
        if value in get_args(annotation):
            return value
        raise ValidationError(
            errors=[{"loc": loc, "msg": f"Unexpected literal value: {value}", "type": "literal_error"}]
        )

    def _validate_leaf(self, annotation: Any, value: Any, loc: list[Any]) -> Any:
        try:
            primitive_validator = self._primitive_validators.get(annotation)
            if primitive_validator is not None:
                return primitive_validator(value)

            if inspect.isclass(annotation) and issubclass(annotation, Enum):
                return annotation(value)

            if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
                if isinstance(value, annotation):
                    return value
                if not isinstance(value, Mapping):
                    raise ValidationError(errors=[{"loc": loc, "msg": "Expected object", "type": "type_error"}])
                return annotation(**value)

            if isinstance(value, annotation):
                return value

            if isinstance(value, Mapping):
                return annotation(**value)

            return annotation(value)
        except ValidationError as exc:
            raise ValidationError(errors=[self._prefix_error(error, loc) for error in exc.errors]) from exc
        except (TypeError, ValueError) as exc:
            raise ValidationError(errors=[{"loc": loc, "msg": str(exc), "type": "type_error"}]) from exc

    def _accepts_none(self, annotation: Any) -> bool:
        origin = get_origin(annotation)
        if origin is None:
            return annotation is type(None)
        return any(arg is type(None) for arg in get_args(annotation))

    def _is_literal(self, annotation: Any) -> bool:
        return get_origin(annotation) is Literal

    def _prefix_error(self, error: dict[str, Any], prefix: list[Any]) -> dict[str, Any]:
        return {
            "loc": [*prefix, *list(error.get("loc", []))],
            "msg": error.get("msg", "Validation error"),
            "type": error.get("type", "type_error"),
        }
