"""Route parameter binding markers.

Use these markers with ``Annotated[T, Body()]`` style annotations.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from modmex import BaseModel

T = TypeVar("T")


class Param(BaseModel, Generic[T]):
    name: str | None = None


class Body(Param[T]):
    pass


class Query(Param[T]):
    pass


class Path(Param[T]):
    pass


class Header(Param[T]):
    pass


class Cookie(Param[T]):
    pass


class RawEvent(Param[T]):
    pass


class LambdaContext(Param[T]):
    pass
