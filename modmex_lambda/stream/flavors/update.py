import os
from typing import Any, Callable, Optional

from reactivex import Observable, operators as ops
from pydash import get, pick
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


class UpdateRule(BaseRule, total=False):
    to_query_request: Callable[[Uow, dict], dict]
    to_get_request: Callable[[Uow, dict], dict]
    to_update_request: Callable[[Uow, dict], dict]
    to_fallback_update_request: Callable[[Uow, dict], dict]
    table_name: str
    split_on: Any
    split_target_field: str
    query_request_field: str
    query_response_field: str
    batch_get_request_field: str
    batch_get_response_field: str
    update_request_field: str
    update_response_field: str
    fallback_update_request_field: str


class Update(BaseFlavor):
    def __init__(
        self,
        rule: UpdateRule,
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
            try_map(lambda uow: self._normalize(uow) if self._for_collected_events(uow) else uow),
            try_filter(on_event_type(self.rule)),
            ops.do_action(print_start(self.logger)),
            try_filter(on_content(self.rule)),
            try_map(faulty(self._to_query_request)),
            self.dynamodb_ops.query(
                **pick({
                    **self.rule,
                    'table_name': self.rule.get(
                        'table_name',
                        os.getenv('ENTITY_TABLE_NAME') or
                        os.getenv('EVENT_TABLE_NAME')
                    )
                }, [
                    'table_name',
                    'query_request_field',
                    'query_response_field'
                ])
            ),
            split_object({
                **self.rule,
                **({
                    'split_on': self.rule.get(
                        'split_on',
                        self.rule.get('query_response_field', 'query_response')
                    ),
                    'split_target_field': self.rule.get(
                        'split_target_field',
                        self.rule.get('query_response_field', 'query_response')
                    )
                } if self.rule.get('split_on') or self.rule.get('to_query_request') else {})
            }),
            try_map(faulty(self._to_get_request)),
            self.dynamodb_ops.batch_get(
                **pick({
                    **self.rule,
                    'table_name': self.rule.get(
                        'table_name',
                        os.getenv('ENTITY_TABLE_NAME') or
                        os.getenv('EVENT_TABLE_NAME')
                    )
                }, [
                    'table_name',
                    'batch_get_request_field',
                    'batch_get_response_field'
                ])
            ),
            try_map(faulty(self._to_update_request)),
            try_map(faulty(self._to_fallback_update_request)),
            self.dynamodb_ops.update(
                **pick({
                    **self.rule,
                    'table_name': self.rule.get(
                        'table_name',
                        os.getenv('ENTITY_TABLE_NAME') or
                        os.getenv('EVENT_TABLE_NAME')
                    )
                }, [
                    'table_name',
                    'update_request_field',
                    'update_response_field',
                    'fallback_update_request_field'
                ])
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

    def _to_query_request(self, uow):
        return {
            **uow,
            'query_request': self.rule['to_query_request'](uow, self.rule)
                if 'to_query_request' in self.rule
                else None
        }

    def _to_get_request(self, uow):
        return {
            **uow,
            'batch_get_request': self.rule['to_get_request'](uow, self.rule)
                if 'to_get_request' in self.rule
                else None
        }

    def _to_update_request(self, uow):
        return {
            **uow,
            'update_request': self.rule['to_update_request'](uow, self.rule)
        }

    def _to_fallback_update_request(self, uow):
        return {
            **uow,
            'fallback_update_request': self.rule['to_fallback_update_request'](uow, self.rule)
                if 'to_fallback_update_request' in self.rule
                else None
        }
