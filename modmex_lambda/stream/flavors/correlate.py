import os
from typing import Any, Callable, Optional

from reactivex import Observable, operators as ops
from pydash import get
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


class CorrelateRule(BaseRule, total=False):
    correlation_key: Any
    correlation_key_suffix: str
    table_name: str
    expire: Any


class Correlate(BaseFlavor):
    def __init__(
        self,
        rule: CorrelateRule,
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
            try_filter(self._for_collected_events),
            try_map(self._normalize),
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

    @staticmethod
    def _for_collected_events(uow):
        return get(uow, 'record.eventName') == 'INSERT' and \
            get(uow, 'record.dynamodb.Keys.sk.S') == 'EVENT'

    @staticmethod
    def _normalize(uow):
        return {
            **uow,
            'meta': {
                'sequence_number': uow['event']['raw']['new']['sequence_number'],
                'ttl': uow['event']['raw']['new']['ttl'],
                'data': uow['event']['raw']['new']['data']
            },
            'event': get(uow, 'event.raw.new.event')
        }

    def _correlation_key(self, uow):
        if callable(self.rule['correlation_key']):
            key = self.rule['correlation_key'](uow)
        else:
            key = get(uow['event'], self.rule['correlation_key'])
        key = f"{key}.{self.rule['correlation_key_suffix']}" \
                if 'correlation_key_suffix' in self.rule \
                else key

        return {
            **uow,
            'key': key
        }

    def _to_put_request(self, uow):
        return {
            **uow,
            "put_request": {
                'Item': {
                    'pk': uow['key'],
                    'sk': uow['event']['id'],
                    'discriminator': 'CORREL',
                    'timestamp': uow['event']['timestamp'],
                    'awsregion': os.getenv('REGION'),
                    'sequence_number': uow['meta']['sequence_number'],
                    'ttl': ttl_rule(self.rule, uow) if self.rule.get('ttl') else uow['meta']['ttl'],
                    'expire': self.rule.get('expire'),
                    'suffix': self.rule.get('correlation_key_suffix'),
                    'rule_id': self.rule.get('id'),
                    'event': uow['event']
                }
            }
        }
