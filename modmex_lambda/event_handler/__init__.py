__all__ = [
    "APIGatewayHttpResolver",
    "APIGatewayRestResolver",
    "Response",
    "DefaultDependencyResolver",
    "DependencyResolver",
    "Depends",
    "InjectorDependencyResolver",
    "content_types",
]


def __getattr__(name):
    target = {
        "APIGatewayHttpResolver": ("modmex_lambda.event_handler.api_gateway", "APIGatewayHttpResolver"),
        "APIGatewayRestResolver": ("modmex_lambda.event_handler.api_gateway", "APIGatewayRestResolver"),
        "Response": ("modmex_lambda.event_handler.api_gateway", "Response"),
        "DefaultDependencyResolver": ("modmex_lambda.dependencies", "DefaultDependencyResolver"),
        "DependencyResolver": ("modmex_lambda.dependencies", "DependencyResolver"),
        "Depends": ("modmex_lambda.event_handler.dependencies.depends", "Depends"),
        "InjectorDependencyResolver": ("modmex_lambda.dependencies", "InjectorDependencyResolver"),
        "content_types": ("modmex_lambda.event_handler.content_types", None),
    }.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    module_name, attr = target
    module = import_module(module_name)
    value = module if attr is None else getattr(module, attr)
    globals()[name] = value
    return value


def __dir__():
    return sorted([*globals().keys(), *__all__])
