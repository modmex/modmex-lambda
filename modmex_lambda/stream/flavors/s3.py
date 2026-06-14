import os
from typing import Any, Callable, Optional

from reactivex import Observable, operators as ops
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.flavors.base_flavor import BaseFlavor
from modmex_lambda.stream.operators.publisher import PublisherOptions
from modmex_lambda.stream.utils.contracts import BaseRule, Uow
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.filters import on_event_type, on_content
from modmex_lambda.stream.utils.operators import try_filter, try_map
from modmex_lambda.stream.utils.print import print_end, print_start
from modmex_lambda.stream.utils.split import split_object


class S3Rule(BaseRule, total=False):
    to_s3: Callable[[Uow], dict]
    bucket_name: str
    split_on: Any
    split_target_field: str


class S3(BaseFlavor):
    def __init__(
        self,
        rule: S3Rule,
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
            try_filter(on_event_type(self.rule)),
            ops.do_action(print_start(self.logger)),
            try_filter(on_content(self.rule)),
            split_object(self.rule),
            try_map(self._to_s3),
            self.s3_ops.put_object(
                bucket_name=self.rule.get('bucket_name') or os.getenv('BUCKET_NAME'),
            ),
            ops.do_action(print_end(self.logger)),
        )

    def _to_s3(self, uow):
        return {
            **uow,
            'put_request': faulty(self.rule['to_s3'])(uow)
        }
