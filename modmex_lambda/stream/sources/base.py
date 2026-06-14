from functools import wraps
from typing import Callable, Optional, TypeVar, Generic, List
from modmex_lambda.dependencies import (
    DependencyResolver,
    default_dependency_resolver,
)
from modmex_lambda.logging import Logger
from modmex_lambda.stream.irules_registry import IRulesRegistry
from modmex_lambda.stream.runner import run
from modmex_lambda.stream.utils.contracts import Uow, Event

S = TypeVar('S', bound=dict)
E = TypeVar('E', bound=Event)

class SourceHandler(Generic[S, E]):
    def __init__(
        self,
        parser: Callable[[S], List[Uow[E]]], # return U
        registry: IRulesRegistry,
        *,
        concurrency: bool = True,
        on_next: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_completed: Optional[Callable] = None,
        logger: Optional[object] = None,
        dependency_resolver: Optional[DependencyResolver] = None,
    ) -> None:
        self.parser = parser
        self.registry = registry
        self.concurrency = concurrency
        self.on_next = on_next
        self.on_error = on_error
        self.on_completed = on_completed
        self.logger = logger or Logger()
        self.dependency_resolver = dependency_resolver or default_dependency_resolver()
        self.registry.bind(self.dependency_resolver)

    def __call__(self, handler: Callable):
        @wraps(handler)
        def wrapper(event: S, context):
            self.handle(event, context)
            return handler(event, context)
        return wrapper
    
    def handle(self, event: S, context):
        self._run(event)
        return {"statusCode": 200}

    def _run(self, event: S):
        run(
            self.parser(event),
            self.registry,
            opt={
                "logger": self.logger,
            },
            on_next=self.on_next,
            on_error=self.on_error,
            on_completed=self.on_completed,
            concurrency=self.concurrency,
        )
