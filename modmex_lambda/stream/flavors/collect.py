import os
from typing import Any, Callable, Optional

from reactivex import Observable, operators as ops
from pydash import get, omit
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.flavors.base_flavor import BaseFlavor
from modmex_lambda.stream.operators.publisher import PublisherOptions
from modmex_lambda.stream.utils.contracts import BaseRule, Uow
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.filters import on_event_type, on_content
from modmex_lambda.stream.utils.time import ttl_rule
from modmex_lambda.stream.utils.operators import try_filter, try_map
from modmex_lambda.stream.utils.print import print_end, print_start


class CollectRule(BaseRule, total=False):
    correlation_key: Any
    to_put_request: Callable[[Uow, dict], dict]
    table_name: str
    expire: Any
    include_raw: bool


class Collect(BaseFlavor):
    def __init__(
        self,
        rule: CollectRule,
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
            try_map(faulty(self._correlation_key)),
            try_map(self._to_put_request),
            self.dynamodb_ops.put(
                table_name=self.rule.get('table_name',
                    os.getenv('ENTITY_TABLE_NAME') or
                    os.getenv('EVENT_TABLE_NAME')
                )
            ),
            ops.do_action(print_end(self.logger)),
        )

    def _correlation_key(self, uow):
        if 'correlation_key' not in self.rule:
            key = uow['event']['partition_key']
        elif callable(self.rule['correlation_key']):
            key = self.rule['correlation_key'](uow)
        else:
            key = get(uow['event'], self.rule['correlation_key'])
        return {
            **uow,
            'key': key
        }

    def _to_put_request(self, uow):
        return {
            **uow,
            "put_request": self.rule['to_put_request'](uow, self.rule)
                if 'to_put_request' in self.rule
                else {
                    'Item': {
                        'pk': uow['event']['id'],
                        'sk': 'EVENT',
                        'discriminator': 'EVENT',
                        'timestamp': uow['event']['timestamp'],
                        'awsregion': os.getenv('REGION'),
                        'sequence_number': self._get_sequence_number(uow),
                        'ttl': ttl_rule(self.rule, uow),
                        'expire': self.rule.get('expire'),
                        'data': uow['key'],
                        'event': uow['event'] if
                                self.rule.get('include_raw') else
                                omit(uow['event'], ['raw'])
                    }
                }
        }

    @staticmethod
    def _get_sequence_number(uow):
        seq = get(uow, 'record.kinesis.sequenceNumber')
        if seq:
            return seq
        seq = get(uow, 'record.attributes.SequenceNumber')
        return seq
