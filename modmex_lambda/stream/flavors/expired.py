from typing import Any, Optional

from reactivex import Observable, operators as ops
from pydash import get
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.flavors.base_flavor import BaseFlavor
from modmex_lambda.stream.operators.publisher import PublisherOptions
from modmex_lambda.stream.utils.contracts import BaseRule
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.operators import try_filter, try_map
from modmex_lambda.stream.utils.print import print_end, print_start


class ExpiredRule(BaseRule, total=False):
    bus_name: str
    source: str


class Expired(BaseFlavor):
    def __init__(
        self,
        rule: ExpiredRule,
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
                'event_field': 'emit',
            },
        )
        self.rule = rule

    @property
    def id(self):
        return self.rule['id']

    def __call__(self, source: Observable):
        return source.pipe(
            try_filter(self._for_expiration),
            ops.do_action(print_start(self.logger)),
            try_map(faulty(self._to_expired_event)),
            self.publisher,
            ops.do_action(print_end(self.logger)),
        )

    @staticmethod
    def _for_expiration(uow):
        if get(uow, 'record.eventName') != 'REMOVE':
            return False

        ttl = get(uow, 'event.raw.old.ttl')
        expire = get(uow, 'event.raw.old.expire')

        if not ttl or not expire:
            return False

        removed = get(uow, 'record.dynamodb.ApproximateCreationDateTime')

        if removed < ttl:
            return False

        return True

    def _to_expired_event(self, uow):
        ttl = get(uow, 'event.raw.old.ttl')
        expire = get(uow, 'event.raw.old.expire')
        event = get(uow, 'event.raw.old.event')

        id_ = event['id']
        type_ = event['type']
        timestamp = event['timestamp']

        return {
            **uow,
            'emit': {
                **event,
                'id': uow['event']['id'],
                'type': self._calc_type(type_, expire),
                'timestamp': (ttl * 1000) + (timestamp % 1000),
                'triggers': [
                    {
                        'id': id_,
                        'type': type_,
                        'timestamp': timestamp
                    }
                ]
            }
        }

    @staticmethod
    def _calc_type(type_, expire):
        if isinstance(expire, str):
            return expire
        if '.' in type_:
            return f"{type_}.expired"
        return f"{type_}-expired"
