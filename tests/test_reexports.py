from __future__ import annotations

import modmex_lambda.exceptions as exceptions
import modmex_lambda.params as params
import modmex_lambda.request as request
import modmex_lambda.resolver as resolver
import modmex_lambda.response as response
import modmex_lambda.routing as routing
from modmex_lambda.event_handler import content_types
from modmex_lambda.event_handler.api_gateway import ApiGatewayHttpResolver, ApiGatewayRestResolver


def test_root_reexport_modules_expose_public_symbols() -> None:
    assert resolver.ApiGatewayHttpResolver is ApiGatewayHttpResolver
    assert resolver.ApiGatewayRestResolver is ApiGatewayRestResolver
    assert response.Response.__name__ == "Response"
    assert request.Request.__name__ == "Request"
    assert routing.Router.__name__ == "Router"
    assert exceptions.NotFoundError().status_code == 404
    assert params.Query.__name__ == "Query"


def test_event_handler_lazy_exports_and_unknown_attribute() -> None:
    import modmex_lambda.event_handler as event_handler

    assert event_handler.ApiGatewayHttpResolver is ApiGatewayHttpResolver
    assert event_handler.content_types is content_types

    try:
        event_handler.missing_symbol
    except AttributeError as exc:
        assert "missing_symbol" in str(exc)
    else:
        raise AssertionError("Expected AttributeError")

    assert "ApiGatewayHttpResolver" in dir(event_handler)
