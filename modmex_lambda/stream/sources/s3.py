from typing import Callable, Optional

from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.events.s3 import (
    from_s3,
    from_sqs_eventbridge_s3,
    from_sqs_sns_s3,
)
from modmex_lambda.stream.irules_registry import IRulesRegistry
from modmex_lambda.stream.sources.base import SourceHandler


class S3Source(SourceHandler):
    def __init__(
        self,
        registry: IRulesRegistry,
        *,
        concurrency: bool = True,
        on_next: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_completed: Optional[Callable] = None,
        on_fault: Optional[Callable] = None,
        logger: Optional[object] = None,
        dependency_resolver: Optional[DependencyResolver] = None,
    ) -> None:
        super().__init__(
            from_s3,
            registry,
            concurrency=concurrency,
            on_next=on_next,
            on_error=on_error,
            on_completed=on_completed,
            on_fault=on_fault,
            logger=logger,
            dependency_resolver=dependency_resolver,
        )


class SqsSnsS3Source(S3Source):
    def __init__(self, registry: IRulesRegistry, **kwargs) -> None:
        super().__init__(registry, **kwargs)
        self.parser = from_sqs_sns_s3


class SqsEventBridgeS3Source(S3Source):
    def __init__(self, registry: IRulesRegistry, **kwargs) -> None:
        super().__init__(registry, **kwargs)
        self.parser = from_sqs_eventbridge_s3


def s3_source(
    registry: IRulesRegistry,
    *,
    concurrency: bool = True,
    on_next: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
    on_completed: Optional[Callable] = None,
    on_fault: Optional[Callable] = None,
    logger: Optional[object] = None,
    dependency_resolver: Optional[DependencyResolver] = None,
):
    return S3Source(
        registry,
        concurrency=concurrency,
        on_next=on_next,
        on_error=on_error,
        on_completed=on_completed,
        on_fault=on_fault,
        logger=logger,
        dependency_resolver=dependency_resolver,
    )


def sqs_sns_s3_source(registry: IRulesRegistry, **kwargs):
    return SqsSnsS3Source(registry, **kwargs)


def sqs_eventbridge_s3_source(registry: IRulesRegistry, **kwargs):
    return SqsEventBridgeS3Source(registry, **kwargs)
