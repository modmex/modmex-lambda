"""Route parameter binding markers.

Use these markers with ``Annotated[T, Body()]`` style annotations.
"""

from __future__ import annotations

from modmex import BaseModel


class Param(BaseModel):
    name: str | None = None


class Body(Param):
    pass


class Query(Param):
    pass


class Path(Param):
    pass


class Header(Param):
    pass


class Cookie(Param):
    pass


class RawEvent(Param):
    pass


class LambdaContext(Param):
    pass
