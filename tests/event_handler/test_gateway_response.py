from __future__ import annotations

from modmex_lambda.data_classes.api_gateway_proxy_event import APIGatewayProxyEvent
from modmex_lambda.event_handler import content_types
from modmex_lambda.event_handler.gateway_response import GatewayResponseBuilder
from modmex_lambda.event_handler.response import Response
from modmex_lambda.event_handler.routing import Router


def test_gateway_response_builder_uses_first_origin_and_response_compression_override() -> None:
    event = APIGatewayProxyEvent(
        {
            "path": "/hello",
            "httpMethod": "GET",
            "headers": {},
            "multiValueHeaders": {
                "origin": ["https://app.example"],
                "accept-encoding": ["gzip"],
            },
            "requestContext": {},
        },
    )
    router = Router()

    @router.route("/hello", method="GET", cors=True, compress=True)
    def hello():
        return {"ok": True}

    route, _, _ = router.match("GET", "/hello")
    response = Response(
        status_code=200,
        body={"ok": True},
        content_type=content_types.APPLICATION_JSON,
        compress=False,
    )

    payload = GatewayResponseBuilder(
        response=response,
        route=route,
        json_serializer=lambda value: '{"ok":true}',
    ).serialize(event)

    assert payload["body"] == '{"ok":true}'
    assert payload["isBase64Encoded"] is False
    assert payload["multiValueHeaders"]["Access-Control-Allow-Origin"] == ["*"]
    assert "Content-Encoding" not in payload["multiValueHeaders"]
