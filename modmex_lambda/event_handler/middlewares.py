from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, Generic

from modmex_lambda.event_handler.response import Response
from modmex_lambda.event_handler.types import EventHandlerInstance, IApiGatewayResolver

__all__ = ["NextMiddleware", "IMiddleware"]


class NextMiddleware(Protocol):
    def __call__(self, app: IApiGatewayResolver) -> Response:
        ...

    @property
    def __name__(self) -> str:
        ...


class IMiddleware(ABC, Generic[EventHandlerInstance]):
    
    @abstractmethod
    def handler(self, app: EventHandlerInstance, next_middleware: NextMiddleware) -> Response:
        raise NotImplementedError()
    
    
    @property
    def __name__(self) -> str:
        return self.__class__.__name__
    
    def __call__(self, app: EventHandlerInstance, next_middleware: NextMiddleware) -> Response:
        return self.handler(app, next_middleware)
