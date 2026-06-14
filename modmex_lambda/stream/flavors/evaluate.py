from functools import reduce
from typing import Any, Callable, Optional

from reactivex import Observable, operators as ops
from pydash import get, pick, omit, merge, sort_by
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.flavors.base_flavor import BaseFlavor
from modmex_lambda.stream.operators.publisher import PublisherOptions
from modmex_lambda.stream.utils.contracts import BaseRule
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.filters import on_event_type, on_content
from modmex_lambda.stream.utils.operators import try_filter, try_map, split_buffer
from modmex_lambda.stream.utils.print import print_end, print_start


class EvaluateRule(BaseRule, total=False):
    correlation_key_suffix: str
    expression: Callable
    emit: Any
    index: str
    table_name: str
    query_request_field: str
    query_response_field: str


class Evaluate(BaseFlavor):
    #pylint: disable=line-too-long
    """
    used to evaluate conditions and produce higher-order events
    used in trigger functions
    *
    {
        'id': str
        'eventType': str | List[str] | Callable, // match rules to events based on event type
        'correlation_key_suffix': Optional[str], // match rules to events based on correlation key suffix
        'filters': Optional[List[Callable]],     // evaluate event content
        'expression': Optional[Callable];       // evaluate correlated events, triggers query for correlated events
        'emit': str | Callable;                 // create higher-order event(s) to publish
        'index': Optional[str];
    }
    """

    def __init__(
        self,
        rule: EvaluateRule,
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
            publisher_options={
                **(publisher_options or {}),
                'event_field': 'emit'
            },
        )
        self.rule = rule

    @property
    def id(self):
        return self.rule['id']

    def __call__(self, source: Observable):
        return source.pipe(
            try_filter(self._for_events),
            try_map(self._normalize),
            try_filter(on_event_type(self.rule)),
            ops.do_action(print_start(self.logger)),
            try_filter(on_content(self.rule)),
            self._complex(),
            try_map(self._to_higher_order_events()),
            split_buffer(),
            self.publisher,
            ops.do_action(print_end(self.logger)),
        )

    @staticmethod
    def _for_events(uow):
        return get(uow, 'record.eventName') == 'INSERT' and \
            (get(uow, 'record.dynamodb.Keys.sk.S') == 'EVENT'
                or get(uow,'record.dynamodb.NewImage.discriminator.S') == 'CORREL'
                )

    @staticmethod
    def _normalize(uow):
        return {
            **uow,
            'meta': {
                'id': get(uow, 'event.id'),
                'sequence_number': get(uow, 'event.raw.new.sequence_number'),
                'ttl': get(uow, 'event.raw.new.ttl'),
                'expire': get(uow, 'event.raw.new.expire'),
                'pk': get(uow, 'event.raw.new.pk'),
                'data': get(uow, 'event.raw.new.data'),
                'correlation_key': get(uow, 'event.raw.new.pk')
                    if get(uow, 'event.raw.new.discriminator') == 'CORREL'
                    else get(uow, 'event.raw.new.data'),
                'suffix': get(uow, 'event.raw.new.suffix'),
                'correlation': get(uow, 'event.raw.new.discriminator') == 'CORREL',
            },
            'event': get(uow, 'event.raw.new.event')
        }

    def _complex(self):
        def wrapper(source: Observable):
            if not self.rule.get('expression'):
                return source.pipe(
                    try_map(lambda uow: {
                        **uow,
                        'triggers': [uow['event']]
                    }),
                )
            return source.pipe(
                try_filter(faulty(self._on_correlation_key_suffix)),
                try_map(self._to_query_request),
                self.dynamodb_ops.query(
                    **pick({
                        **self.rule,
                        'query_response_field': 'correlated'
                    }, [
                        'table_name',
                        'query_request_field',
                        'query_response_field'
                    ])
                ),
                try_map(lambda uow: {
                    **uow,
                    'correlated': sort_by(
                        [i['event'] for i in uow['correlated']],
                        'timestamp',
                        reverse=True
                    )
                }),
                try_map(faulty(self._expression)),
                try_filter(lambda uow: uow['expression'])
            )
        return wrapper

    def _on_correlation_key_suffix(self, uow):
        if not self.rule.get('correlation_key_suffix') and \
            not get(uow, 'meta.suffix'):
            return True

        if self.rule.get('correlation_key_suffix') and \
            not get(uow, 'meta.suffix'):
            return False

        if self.rule.get('correlation_key_suffix') and \
            get(uow, 'meta.suffix') == self.rule.get('correlation_key_suffix'):
            return True
        return False

    def _to_query_request(self, uow):
        return {
            **uow,
            'query_request': {
                'KeyConditionExpression': '#pk = :pk',
                'ExpressionAttributeNames': {
                    '#pk': 'pk',
                },
                'ExpressionAttributeValues': {
                    ':pk': get(uow, 'meta.pk'),
                },
                'ConsistentRead': True
            } if get(uow, 'meta.correlation')
            else {
                'IndexName': self.rule.get('index', 'DataIndex'),
                'KeyConditionExpression': '#data = :data',
                'ExpressionAttributeNames': {
                    '#data': 'data',
                },
                'ExpressionAttributeValues': {
                    ':data': get(uow, 'meta.data'),
                },
            },
        }

    def _expression(self, uow):
        result = self.rule['expression'](uow)
        return {
            **uow,
            'expression': len(result) > 0 if isinstance(result, list) else result,
            'triggers': [uow['event']] if isinstance(result, bool) else self._cast_array(result)
        }

    @staticmethod
    def _cast_array(value):
        if isinstance(value, list):
            return value
        return [value]

    def _to_higher_order_events(self):
        def wrapper(uow):
            basic = isinstance(self.rule['emit'], str)
            trigger = uow['triggers'][-1]
            template = {
                **(uow['event'] if basic else {} ),
                'id': f"{get(uow,'meta.id')}.{self.rule['id']}",
                'type': self.rule['emit'] if basic else None,
                'timestamp': trigger['timestamp'],
                'partition_key': get(uow, 'meta.correlation_key').replace(
                    f".{self.rule.get('correlation_key_suffix')}",
                    ""
                ),
                'tags': omit(
                    reduce(
                        lambda previous, current: merge(previous, current.get('tags')),
                        uow['triggers'],
                        {}
                    ),
                    ['region', 'source']
                ),
                'triggers': [
                    {
                        'id': i['id'],
                        'type': i['type'],
                        'timestamp': i['timestamp']
                    }
                    for i in uow['triggers']
                ]
            }
            result =  template if basic else self.rule['emit'](uow, self.rule, template)
            return [
                {
                    **uow,
                    'emit': emit
                }
                for emit in self._cast_array(result)
            ]
        return faulty(wrapper)
