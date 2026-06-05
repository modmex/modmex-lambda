from __future__ import annotations

from modmex_lambda.data_classes.api_gateway_proxy_event import APIGatewayProxyEvent, APIGatewayProxyEventV2
from modmex_lambda.data_classes.api_gateway_websocket_event import APIGatewayWebSocketEvent


def test_rest_proxy_event_exposes_gateway_fields_and_serializers() -> None:
    event = APIGatewayProxyEvent(
        {
            "resource": "/users",
            "path": "/users/1",
            "httpMethod": "GET",
            "headers": {"X-One": "1"},
            "multiValueHeaders": {"X-Many": ["a", "b"]},
            "queryStringParameters": {"q": "one,two", "page": "1"},
            "multiValueQueryStringParameters": {"q": ["one", "two"]},
            "pathParameters": {"id": "1"},
            "stageVariables": {"stage": "prod"},
            "requestContext": {
                "accountId": "123",
                "resourceId": "res",
                "apiId": "api",
                "domainName": "api.example",
                "domainPrefix": "api",
                "extendedRequestId": "ext",
                "requestId": "req",
                "protocol": "HTTP/1.1",
                "stage": "prod",
                "requestTime": "now",
                "requestTimeEpoch": 1,
                "path": "/prod/users/1",
                "resourcePath": "/users/{id}",
                "httpMethod": "GET",
                "connectedAt": 1,
                "connectionId": "conn",
                "eventType": "MESSAGE",
                "messageDirection": "IN",
                "messageId": "msg",
                "operationName": "op",
                "routeKey": "GET /users",
                "identity": {"sourceIp": "127.0.0.1"},
                "authorizer": {"claims": {"sub": "user"}, "scopes": ["read"], "principalId": "p"},
            },
        },
    )

    assert event.version == "1.0"
    assert event.resource == "/users"
    assert event.resolved_query_string_parameters == {"q": ["one", "two"], "page": ["1"]}
    assert event.resolved_headers_field["x-many"] == ["a", "b"]
    assert event.path_parameters == {"id": "1"}
    assert event.stage_variables == {"stage": "prod"}
    assert event.request_context.account_id == "123"
    assert event.request_context.api_id == "api"
    assert event.request_context.domain_name == "api.example"
    assert event.request_context.domain_prefix == "api"
    assert event.request_context.extended_request_id == "ext"
    assert event.request_context.protocol == "HTTP/1.1"
    assert event.request_context.http_method == "GET"
    assert event.request_context.path == "/prod/users/1"
    assert event.request_context.stage == "prod"
    assert event.request_context.request_id == "req"
    assert event.request_context.request_time == "now"
    assert event.request_context.request_time_epoch == 1
    assert event.request_context.resource_id == "res"
    assert event.request_context.resource_path == "/users/{id}"
    assert event.request_context.connected_at == 1
    assert event.request_context.connection_id == "conn"
    assert event.request_context.event_type == "MESSAGE"
    assert event.request_context.message_direction == "IN"
    assert event.request_context.message_id == "msg"
    assert event.request_context.operation_name == "op"
    assert event.request_context.route_key == "GET /users"
    assert event.request_context.identity.source_ip == "127.0.0.1"
    assert event.request_context.authorizer.claims == {"sub": "user"}
    assert event.request_context.authorizer.scopes == ["read"]
    assert event.request_context.authorizer.principal_id == "p"
    assert event.request_context.authorizer.integration_latency is None
    assert event.request_context.authorizer.get_context() == {
        "claims": {"sub": "user"},
        "scopes": ["read"],
        "principalId": "p",
    }
    assert event.header_serializer().serialize({"x": "1"}, []) == {"multiValueHeaders": {"x": ["1"]}}

    only_multi = APIGatewayProxyEvent(
        {
            "path": "/users",
            "httpMethod": "GET",
            "headers": {},
            "multiValueHeaders": {},
            "multiValueQueryStringParameters": {"tag": ["a"]},
            "requestContext": {},
        },
    )
    assert only_multi.resolved_query_string_parameters == {"tag": ["a"]}


def test_http_proxy_event_v2_exposes_stage_path_cookies_authorizer_and_headers() -> None:
    event = APIGatewayProxyEventV2(
        {
            "version": "2.0",
            "routeKey": "GET /users",
            "rawPath": "/prod/users",
            "rawQueryString": "q=1",
            "headers": {"accept": "application/json,text/plain"},
            "queryStringParameters": {"q": "1,2"},
            "cookies": ["session=abc", "theme=dark"],
            "pathParameters": {"id": "1"},
            "stageVariables": {"env": "prod"},
            "requestContext": {
                "accountId": "123",
                "apiId": "api",
                "domainName": "api.example",
                "domainPrefix": "api",
                "requestId": "req",
                "routeKey": "GET /users",
                "stage": "prod",
                "time": "now",
                "timeEpoch": 1,
                "http": {
                    "method": "GET",
                    "path": "/prod/users",
                    "protocol": "HTTP/1.1",
                    "sourceIp": "127.0.0.1",
                    "userAgent": "pytest",
                },
                "authorizer": {
                    "jwt": {"claims": {"sub": "user"}, "scopes": ["read"]},
                    "lambda": {"tenant": "mx"},
                    "iam": {"accessKey": "ak", "cognitoIdentity": {"amr": ["pwd"]}},
                },
            },
        },
    )

    assert event.version == "2.0"
    assert event.route_key == "GET /users"
    assert event.raw_path == "/prod/users"
    assert event.raw_query_string == "q=1"
    assert event.path == "/users"
    assert event.http_method == "GET"
    assert event.resolved_cookies_field == {"session": "abc", "theme": "dark"}
    assert event.resolved_headers_field["accept"] == ["application/json", "text/plain"]
    assert event.path_parameters == {"id": "1"}
    assert event.stage_variables == {"env": "prod"}
    assert event.request_context.http.source_ip == "127.0.0.1"
    assert event.request_context.account_id == "123"
    assert event.request_context.api_id == "api"
    assert event.request_context.domain_name == "api.example"
    assert event.request_context.domain_prefix == "api"
    assert event.request_context.request_id == "req"
    assert event.request_context.route_key == "GET /users"
    assert event.request_context.stage == "prod"
    assert event.request_context.time == "now"
    assert event.request_context.time_epoch == 1
    assert event.request_context.http.method == "GET"
    assert event.request_context.http.path == "/prod/users"
    assert event.request_context.http.protocol == "HTTP/1.1"
    assert event.request_context.http.user_agent == "pytest"
    assert event.request_context.authorizer.jwt_claim == {"sub": "user"}
    assert event.request_context.authorizer.jwt_scopes == ["read"]
    assert event.request_context.authorizer.get_context() == {"tenant": "mx"}
    assert event.request_context.authorizer.iam.access_key == "ak"
    assert event.request_context.authorizer.iam.account_id == ""
    assert event.request_context.authorizer.iam.caller_id == ""
    assert event.request_context.authorizer.iam.cognito_amr == ["pwd"]
    assert event.request_context.authorizer.iam.cognito_identity_id == ""
    assert event.request_context.authorizer.iam.cognito_identity_pool_id == ""
    assert event.request_context.authorizer.iam.principal_org_id == ""
    assert event.request_context.authorizer.iam.user_arn == ""
    assert event.request_context.authorizer.iam.user_id == ""
    assert event.header_serializer().serialize({"x": ["1", "2"]}, []) == {
        "headers": {"x": "1, 2"},
        "cookies": [],
    }


def test_websocket_event_parses_json_and_falls_back_to_raw_body() -> None:
    event = APIGatewayWebSocketEvent(
        {
            "requestContext": {"routeKey": "$default", "eventType": "MESSAGE", "connectionId": "conn"},
            "body": '{"message":"hello"}',
        },
    )
    invalid = APIGatewayWebSocketEvent({"body": "not-json"})
    passthrough = APIGatewayWebSocketEvent({"body": {"already": "decoded"}})

    assert event.request_context == {"routeKey": "$default", "eventType": "MESSAGE", "connectionId": "conn"}
    assert event.route_key == "$default"
    assert event.event_type == "MESSAGE"
    assert event.connection_id == "conn"
    assert event.body == '{"message":"hello"}'
    assert event.json_body == {"message": "hello"}
    assert invalid.json_body == "not-json"
    assert passthrough.json_body == {"already": "decoded"}
