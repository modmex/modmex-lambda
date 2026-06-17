from __future__ import annotations

import modmex_lambda
import modmex_lambda.exceptions as exceptions
import modmex_lambda.params as params
import modmex_lambda.request as request
import modmex_lambda.resolver as resolver
import modmex_lambda.response as response
import modmex_lambda.routing as routing
from modmex_lambda.connectors import AwsConnectorsModule
from modmex_lambda.dependencies import InjectorDependencyResolver, create_dependency_resolver
from modmex_lambda.event_handler import content_types
from modmex_lambda.event_handler.api_gateway import APIGatewayHttpResolver, APIGatewayRestResolver
from modmex_lambda.tracing import Tracer


def test_root_reexport_modules_expose_public_symbols() -> None:
    assert resolver.APIGatewayHttpResolver is APIGatewayHttpResolver
    assert resolver.APIGatewayRestResolver is APIGatewayRestResolver
    assert response.Response.__name__ == "Response"
    assert request.Request.__name__ == "Request"
    assert routing.Router.__name__ == "Router"
    assert exceptions.NotFoundError().status_code == 404
    assert params.Query.__name__ == "Query"
    assert modmex_lambda.AwsConnectorsModule is AwsConnectorsModule
    assert modmex_lambda.InjectorDependencyResolver is InjectorDependencyResolver
    assert modmex_lambda.create_dependency_resolver is create_dependency_resolver
    assert modmex_lambda.Tracer is Tracer


def test_event_handler_lazy_exports_and_unknown_attribute() -> None:
    import modmex_lambda.event_handler as event_handler

    assert event_handler.APIGatewayHttpResolver is APIGatewayHttpResolver
    assert event_handler.content_types is content_types

    try:
        event_handler.missing_symbol
    except AttributeError as exc:
        assert "missing_symbol" in str(exc)
    else:
        raise AssertionError("Expected AttributeError")

    assert "APIGatewayHttpResolver" in dir(event_handler)
