from __future__ import annotations

import json


def rest_event(
    method: str = "GET",
    path: str = "/",
    *,
    headers: dict[str, str] | None = None,
    multi_value_headers: dict[str, list[str]] | None = None,
    query: dict[str, str] | None = None,
    multi_value_query: dict[str, list[str]] | None = None,
    body: object = None,
) -> dict:
    encoded_body = json.dumps(body) if isinstance(body, (dict, list)) else body
    return {
        "httpMethod": method,
        "path": path,
        "headers": headers or {},
        "multiValueHeaders": multi_value_headers,
        "queryStringParameters": query,
        "multiValueQueryStringParameters": multi_value_query,
        "pathParameters": None,
        "body": encoded_body,
        "isBase64Encoded": False,
        "requestContext": {
            "stage": "$default",
            "http": {"method": method, "path": path},
            "routeKey": f"{method} {path}",
        },
    }


def http_v2_event(
    method: str = "GET",
    path: str = "/",
    *,
    headers: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
    body: object = None,
) -> dict:
    encoded_body = json.dumps(body) if isinstance(body, (dict, list)) else body
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": headers or {},
        "queryStringParameters": query,
        "cookies": ["session=abc"],
        "body": encoded_body,
        "isBase64Encoded": False,
        "requestContext": {
            "stage": "$default",
            "http": {"method": method, "path": path},
            "routeKey": f"{method} {path}",
        }
    }


def response_body(response: dict) -> object:
    return json.loads(response["body"]) if response["body"] else None
