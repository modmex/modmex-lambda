import os
from typing import Callable, Optional, Any

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


class SnsRule(BaseRule, total=False):
    to_sns: Callable[[Uow], dict]
    topic_arn: str


class Sns(BaseFlavor):
    def __init__(
        self,
        rule: SnsRule,
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
            try_map(self._to_sns),
            self.sns_ops.publish(
                topic_arn=self.rule.get('topic_arn') or os.getenv('TOPIC_ARN'),
            ),
            ops.do_action(print_end(self.logger)),
        )

    def _to_sns(self, uow):
        return faulty(lambda item: {
            **item,
            'sns_payload': self.rule['to_sns'](item)
        })(uow)
