from __future__ import annotations

from datetime import datetime

from modmex_lambda.shared.cookies import Cookie, SameSite
from modmex_lambda.shared.headers_serializer import HttpApiHeadersSerializer, MultiValueHeadersSerializer


def test_cookie_string_includes_configured_attributes() -> None:
    cookie = Cookie(
        "session",
        "abc",
        path="/",
        domain="example.com",
        expires=datetime(2026, 1, 2, 3, 4, 5),
        max_age=-1,
        http_only=True,
        same_site=SameSite.STRICT_MODE,
        custom_attributes=["Priority=High"],
    )

    assert str(cookie) == (
        "session=abc; Path=/; Domain=example.com; Expires=Fri, 02 Jan 2026 03:04:05 GMT; "
        "Max-Age=0; HttpOnly; Secure; SameSite=Strict; Priority=High"
    )


def test_header_serializers_skip_none_and_handle_repeated_values() -> None:
    cookie = Cookie("seen", "true")
    headers = {"x-one": "1", "x-many": ["a", "b"], "x-skip": None}

    http = HttpApiHeadersSerializer().serialize(headers, [cookie])
    rest = MultiValueHeadersSerializer().serialize(headers, [cookie])

    assert http == {
        "headers": {"x-one": "1", "x-many": "a, b"},
        "cookies": ["seen=true; Secure"],
    }
    assert rest == {
        "multiValueHeaders": {
            "x-one": ["1"],
            "x-many": ["a", "b"],
            "Set-Cookie": ["seen=true; Secure"],
        },
    }


def test_cookie_positive_max_age() -> None:
    assert str(Cookie("session", "abc", max_age=60)) == "session=abc; Max-Age=60; Secure"
