from typing import Callable, Optional

from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.events.sqs import from_sqs
from modmex_lambda.stream.irules_registry import IRulesRegistry
from modmex_lambda.stream.sources.base import SourceHandler


class SqsSource(SourceHandler):
    def __init__(
        self,
        registry: IRulesRegistry,
        *,
        concurrency: bool = True,
        on_next: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_completed: Optional[Callable] = None,
        logger: Optional[object] = None,
        dependency_resolver: Optional[DependencyResolver] = None,
    ) -> None:
        super().__init__(
            from_sqs,
            registry,
            concurrency=concurrency,
            on_next=on_next,
            on_error=on_error,
            on_completed=on_completed,
            logger=logger,
            dependency_resolver=dependency_resolver,
        )


def sqs_source(
    registry: IRulesRegistry,
    *,
    concurrency: bool = True,
    on_next: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
    on_completed: Optional[Callable] = None,
    logger: Optional[object] = None,
    dependency_resolver: Optional[DependencyResolver] = None,
):
    return SqsSource(
        registry,
        concurrency=concurrency,
        on_next=on_next,
        on_error=on_error,
        on_completed=on_completed,
        logger=logger,
        dependency_resolver=dependency_resolver,
    )
