"""API Gateway response helpers."""

from __future__ import annotations

from typing import TypeVar, Generic, Mapping
from modmex_lambda.shared.cookies import Cookie




T = TypeVar("T")


class Response(Generic[T]):
    """Response data class that provides greater control over what is returned from the proxy event"""

    def __init__(
        self,
        status_code: int,
        content_type: str | None = None,
        body: T | None = None,
        headers: Mapping[str, str | list[str]] | None = None,
        cookies: list[Cookie] | None = None,
        compress: bool | None = None,
    ):
        """

        Parameters
        ----------
        status_code: int
            Http status code, example 200
        content_type: str
            Optionally set the Content-Type header, example "application/json". Note this will be merged into any
            provided http headers
        body: str | bytes | None
            Optionally set the response body. Note: bytes body will be automatically base64 encoded
        headers: Mapping[str, str | list[str]]
            Optionally set specific http headers. Setting "Content-Type" here would override the `content_type` value.
        cookies: list[Cookie]
            Optionally set cookies.
        """
        self.status_code = status_code
        self.body = body
        self.base64_encoded = False
        self.headers: dict[str, str | list[str]] = dict(headers) if headers else {}
        self.cookies = cookies or []
        self.compress = compress
        self.content_type = content_type
        if content_type:
            self.headers.setdefault("Content-Type", content_type)

    def is_json(self) -> bool:
        """
        Helper method to check if the response content type is JSON
        """
        content_type = self.headers.get("Content-Type", "")
        if isinstance(content_type, list):
            content_type = content_type[0]
        return content_type.startswith("application/json")

