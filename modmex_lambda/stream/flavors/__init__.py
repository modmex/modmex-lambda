from importlib import import_module
from typing import Any

_EXPORTS = {
    "Schedule": ("modmex_lambda.stream.flavors.schedule", "Schedule"),
    "ScheduleRule": ("modmex_lambda.stream.flavors.schedule", "ScheduleRule"),
}

__all__ = list(_EXPORTS)


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
