import os
from typing import Any, Callable, Optional

from reactivex import Observable, operators as ops
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.filters.latch import out_source_is_self
from modmex_lambda.stream.flavors.base_flavor import BaseFlavor
from modmex_lambda.stream.operators.publisher import PublisherOptions
from modmex_lambda.stream.utils.contracts import BaseRule, Uow
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.filters import on_event_type, on_content
from modmex_lambda.stream.utils.operators import try_filter, try_map
from modmex_lambda.stream.utils.print import print_end, print_start
from modmex_lambda.stream.utils.split import split_object


class MaterializeRule(BaseRule, total=False):
    to_update_request: Callable[[Uow], dict]
    split_on: Any
    split_target_field: str


class Materialize(BaseFlavor):
    def __init__(
        self,
        rule: MaterializeRule,
        *,
        logger: Optional[Any] = None,
        connector: Optional[IEventBridgeConnector] = None,
        dependency_resolver: Optional[DependencyResolver] = None,
        publisher_options: Optional[PublisherOptions] = None,
    ) -> None:
        super().__init__(
            logger=logger,
            connector=connector,
            dependency_resolver=dependency_resolver,
            publisher_options=publisher_options,
        )
        self.rule = rule

    @property
    def id(self):
        return self.rule['id']

    def __call__(self, source: Observable):
        return source.pipe(
            try_filter(out_source_is_self),
            try_filter(on_event_type(self.rule)),
            ops.do_action(print_start(self.logger)),
            try_filter(on_content(self.rule)),
            split_object(self.rule),
            try_map(self._to_update_request),
            self.dynamodb_ops.update(
                table_name=os.getenv('ENTITY_TABLE_NAME') or
                           os.getenv('EVENT_TABLE_NAME'),
            ),
            ops.do_action(print_end(self.logger)),
        )

    def _to_update_request(self, uow):
        return {
            **uow,
            "update_request": faulty(self.rule['to_update_request'])(uow)
        }
