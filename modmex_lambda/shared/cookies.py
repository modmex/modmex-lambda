from __future__ import annotations

from enum import Enum
from io import StringIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class SameSite(Enum):

    DEFAULT_MODE = ""
    LAX_MODE = "Lax"
    STRICT_MODE = "Strict"
    NONE_MODE = "None"


def _format_date(timestamp: datetime) -> str:
    return timestamp.strftime("%a, %d %b %Y %H:%M:%S GMT")


class Cookie:

    def __init__(
        self,
        name: str,
        value: str,
        path: str = "",
        domain: str = "",
        secure: bool = True,
        http_only: bool = False,
        max_age: int | None = None,
        expires: datetime | None = None,
        same_site: SameSite | None = None,
        custom_attributes: list[str] | None = None,
    ):

        self.name = name
        self.value = value
        self.path = path
        self.domain = domain
        self.secure = secure
        self.expires = expires
        self.max_age = max_age
        self.http_only = http_only
        self.same_site = same_site
        self.custom_attributes = custom_attributes

    def __str__(self) -> str:
        payload = StringIO()
        payload.write(f"{self.name}={self.value}")

        if self.path:
            payload.write(f"; Path={self.path}")

        if self.domain:
            payload.write(f"; Domain={self.domain}")

        if self.expires:
            payload.write(f"; Expires={_format_date(self.expires)}")

        if self.max_age:
            if self.max_age > 0:
                payload.write(f"; Max-Age={self.max_age}")
            else:
                # negative or zero max-age should be set to 0
                payload.write("; Max-Age=0")

        if self.http_only:
            payload.write("; HttpOnly")

        if self.secure:
            payload.write("; Secure")

        if self.same_site:
            payload.write(f"; SameSite={self.same_site.value}")

        if self.custom_attributes:
            for attr in self.custom_attributes:
                payload.write(f"; {attr}")

        return payload.getvalue()

