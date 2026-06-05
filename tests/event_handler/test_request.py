from __future__ import annotations

from modmex_lambda.data_classes.api_gateway_proxy_event import APIGatewayProxyEvent, APIGatewayProxyEventV2
from modmex_lambda.event_handler.request import Request
from tests.conftest import http_v2_event, rest_event


def test_request_facade_exposes_http_v2_event_values() -> None:
    event = APIGatewayProxyEventV2(
        http_v2_event(
            "POST",
            "/orders/42",
            headers={"X-Tenant": "mx"},
            query={"debug": "1"},
            body={"name": "Ada"},
        ),
    )

    request = Request(
        route_path="/orders/<order_id>",
        path_parameters={"order_id": "42"},
        current_event=event,
        context={"trace_id": "abc"},
    )

    assert request.route == "/orders/<order_id>"
    assert request.path_parameters == {"order_id": "42"}
    assert request.method == "POST"
    assert request.headers["x-tenant"] == "mx"
    assert request.query_parameters == {"debug": "1"}
    assert request.body == '{"name": "Ada"}'
    assert request.json_body == {"name": "Ada"}
    assert request.resolved_event is event
    assert request.current_event is event
    assert request.context == {"trace_id": "abc"}


def test_request_facade_exposes_rest_event_values() -> None:
    event = APIGatewayProxyEvent(
        rest_event(
            "GET",
            "/users/7",
            headers={"X-Tenant": "mx"},
            query={"active": "true"},
        ),
    )

    request = Request(route_path="/users/<user_id>", path_parameters={"user_id": "7"}, current_event=event)

    assert request.method == "GET"
    assert request.headers["x-tenant"] == "mx"
    assert request.query_parameters == {"active": "true"}
    assert request.json_body is None

