__all__ = [
    "DefaultDependencyResolver",
    "DependencyResolver",
    "Depends",
    "InjectorDependencyResolver",
]


def __getattr__(name):
    target = {
        "DefaultDependencyResolver": ("modmex_lambda.dependencies", "DefaultDependencyResolver"),
        "DependencyResolver": ("modmex_lambda.dependencies", "DependencyResolver"),
        "Depends": ("modmex_lambda.event_handler.dependencies.depends", "Depends"),
        "InjectorDependencyResolver": ("modmex_lambda.dependencies", "InjectorDependencyResolver"),
    }.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    module_name, attr = target
    value = getattr(import_module(module_name), attr)
    globals()[name] = value
    return value


def __dir__():
    return sorted([*globals().keys(), *__all__])
