"""event source decorator."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TYPE_CHECKING

from modmex_lambda.parser import parse

if TYPE_CHECKING:
    from .validation import Validator


def event_source(
    *,
    data_class: type,
    model: Any | None = None,
    source: str | None = None,
    validator: "Validator | None" = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap raw Lambda event with a data class and optionally parse nested payloads."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(event: dict[str, Any], context: object, *args: Any, **kwargs: Any) -> Any:
            wrapped_event = data_class(event)
            if model is not None and source:
                _parse_nested_payloads(wrapped_event, model=model, source=source, validator=validator)
            return func(wrapped_event, context, *args, **kwargs)

        return wrapper

    return decorator


def _parse_nested_payloads(wrapped_event: Any, *, model: Any, source: str, validator: "Validator | None") -> None:
    parsed_attr = f"parsed_{source}"

    records = getattr(wrapped_event, "records", None)
    if records is not None:
        for record in records:
            value = getattr(record, source)
            parsed = parse(event=value, model=model, validator=validator)
            setattr(record, parsed_attr, parsed)
        return

    if hasattr(wrapped_event, source):
        value = getattr(wrapped_event, source)
        parsed = parse(event=value, model=model, validator=validator)
        setattr(wrapped_event, parsed_attr, parsed)


__all__ = ["event_source"]
