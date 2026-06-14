from typing import Callable, Optional, TypedDict

from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.events.dynamodb import from_dynamodb
from modmex_lambda.stream.irules_registry import IRulesRegistry
from modmex_lambda.stream.sources.base import SourceHandler
from modmex_lambda.stream.utils.data_classes.dynamodb import DynamoDBStreamEvent
from modmex_lambda.stream.utils.contracts import DynamoDBEvent

class DynamodbParserOptions(TypedDict, total=False):
    pk_fn: str
    sk_fn: str
    discriminator_fn: str
    event_type_prefix: Optional[str]



class DynamoDBSource(SourceHandler[DynamoDBStreamEvent, DynamoDBEvent]):
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
        parser_options: Optional[DynamodbParserOptions] = None,

    ) -> None:
        options = parser_options or {}
        super().__init__(
            lambda event: from_dynamodb(
                event,
                pk_fn=options.get("pk_fn", "pk"),
                sk_fn=options.get("sk_fn", "sk"),
                discriminator_fn=options.get("discriminator_fn", "discriminator"),
                event_type_prefix=options.get("event_type_prefix"),
            ),
            registry,
            concurrency=concurrency,
            on_next=on_next,
            on_error=on_error,
            on_completed=on_completed,
            logger=logger,
            dependency_resolver=dependency_resolver,
        )


def dynamodb_source(
    registry: IRulesRegistry,
    *,
    concurrency: bool = True,
    on_next: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
    on_completed: Optional[Callable] = None,
    logger: Optional[object] = None,
    dependency_resolver: Optional[DependencyResolver] = None,
    parser_options: Optional[DynamodbParserOptions] = None,
):
    return DynamoDBSource(
        registry,
        concurrency=concurrency,
        on_next=on_next,
        on_error=on_error,
        on_completed=on_completed,
        logger=logger,
        dependency_resolver=dependency_resolver,
        parser_options=parser_options,
    )
