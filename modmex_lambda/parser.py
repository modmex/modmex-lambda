"""Lightweight event parser APIs."""

from __future__ import annotations

import json
from functools import wraps
from typing import Any, Callable, TYPE_CHECKING

from modmex.errors import ValidationError

if TYPE_CHECKING:
    from .validation import Validator


def parse(*, event: Any, model: Any, validator: "Validator | None" = None) -> Any:
    """Validate/transform a raw event into ``model`` using the selected validator."""
    selected_validator = validator
    if selected_validator is None:
        from .validation import ModmexValidator

        selected_validator = ModmexValidator()

    raw_event = event
    if isinstance(event, str):
        try:
            raw_event = json.loads(event)
        except json.JSONDecodeError as exc:
            raise ValidationError(errors=[{"loc": [], "msg": str(exc), "type": "value_error.jsondecode"}]) from exc

    return selected_validator.validate(raw_event, model)


def event_parser(*, model: Any, validator: "Validator | None" = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that parses Lambda ``event`` into ``model`` before handler execution."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(event: Any, context: object, *args: Any, **kwargs: Any) -> Any:
            parsed_event = parse(event=event, model=model, validator=validator)
            return func(parsed_event, context, *args, **kwargs)

        return wrapper

    return decorator


__all__ = ["parse", "event_parser"]
