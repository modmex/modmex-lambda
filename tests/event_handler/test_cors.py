from __future__ import annotations

from modmex_lambda.event_handler.cors import CORSConfig


def test_cors_config_builds_headers_for_allowed_origin() -> None:
    cors = CORSConfig(
        allow_origin="https://app.example",
        extra_origins=["https://admin.example"],
        allow_headers=["X-Tenant-Id"],
        expose_headers=["X-Trace-Id"],
        max_age=3600,
        allow_credentials=True,
    )

    assert cors.allowed_origin("https://admin.example") == "https://admin.example"
    assert cors.to_dict("https://app.example") == {
        "Access-Control-Allow-Origin": "https://app.example",
        "Access-Control-Allow-Headers": (
            "Authorization,Content-Type,X-Amz-Date,X-Amz-Security-Token,X-Api-Key,X-Tenant-Id"
        ),
        "Access-Control-Expose-Headers": "X-Trace-Id",
        "Access-Control-Max-Age": "3600",
        "Access-Control-Allow-Credentials": "true",
    }


def test_cors_config_omits_headers_for_missing_or_disallowed_origin() -> None:
    cors = CORSConfig(allow_origin="https://app.example")

    assert cors.to_dict(None) == {}
    assert cors.to_dict("https://evil.example") == {}
    assert cors.allowed_origin("https://evil.example") is None


def test_cors_wildcard_origin() -> None:
    cors = CORSConfig()

    assert cors.allowed_origin("https://app.example") == "*"
    assert cors.to_dict("*") == {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Authorization,Content-Type,X-Amz-Date,X-Amz-Security-Token,X-Api-Key",
    }
    assert CORSConfig.build_allow_methods({"POST", "GET"}) == "GET,POST"
