from __future__ import annotations

from modmex_lambda.event_handler.response import Response
from modmex_lambda.shared.cookies import Cookie


def test_response_sets_content_type_header_when_provided() -> None:
    response = Response(status_code=201, content_type="application/json", body={"ok": True})

    assert response.status_code == 201
    assert response.headers == {"Content-Type": "application/json"}
    assert response.is_json() is True


def test_response_keeps_explicit_content_type_header() -> None:
    response = Response(
        status_code=200,
        content_type="application/json",
        headers={"Content-Type": "application/vnd.api+json"},
        body={},
    )

    assert response.headers["Content-Type"] == "application/vnd.api+json"
    assert response.is_json() is False


def test_response_tracks_binary_and_cookie_options() -> None:
    cookie = Cookie("seen", "true")
    response = Response(status_code=200, body=b"ok", cookies=[cookie], compress=True)

    assert response.body == b"ok"
    assert response.base64_encoded is False
    assert response.cookies == [cookie]
    assert response.compress is True

