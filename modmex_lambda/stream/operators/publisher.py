import os
import json
from typing import Generic, Optional, TypeVar
from typing import TypedDict

from reactivex import Observable, operators as ops

from modmex_lambda.connectors.eventbridge import Connector
from modmex_lambda.logging import Logger
from modmex_lambda.stream.operators.ioperator import IOperator
from modmex_lambda.stream.utils.contracts import BatchUow, Event, Uow
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.stream.utils.json_encoder import JSONEncoder
from modmex_lambda.stream.utils.operators import split_buffer
from modmex_lambda.stream.utils.operators import try_map
from modmex_lambda.stream.utils.tags import adorn_standard_tags
from modmex_lambda.stream.utils.batch import to_batch_uow, unbatch_uow

TEvent = TypeVar("TEvent", bound=Event)


class PublisherOptions(TypedDict, total=False):
    bus_name: str
    source: str
    publish_request_entry_field: str
    publish_request_field: str
    batch_size: int
    event_field: str


class Publisher(Generic[TEvent], IOperator[Uow[TEvent]]):

    def __init__(
        self,
        connector: Optional[IEventBridgeConnector] = None,
        bus_name=None,
        source: Optional[str] = None,
        event_field: Optional[str] = None,
        publish_request_entry_field: Optional[str] = None,
        publish_request_field: Optional[str] = None,
        batch_size: Optional[int] = None,
        logger: Optional[object] = None,
    ):
        self.connector = connector or Connector()
        self.bus_name = bus_name or os.getenv('BUS_NAME')
        self.source = source or os.getenv('BUS_SRC') or 'custom'
        self.event_field = event_field or 'event'
        self.publish_request_entry_field = publish_request_entry_field or 'publish_request_entry'
        self.publish_request_field = publish_request_field or 'publish_request'
        self.batch_size = int(
            batch_size or os.getenv('PUBLISH_BATCH_SIZE') or os.getenv('BATCH_SIZE') or 10
        )
        self.logger = logger or Logger()

    def __call__(self, source: Observable[Uow[TEvent]]):
        return source.pipe(
            try_map(adorn_standard_tags(self.event_field)),
            try_map(self._to_publish_request_entry),
            ops.buffer_with_count(self.batch_size, self.batch_size),
            try_map(to_batch_uow),
            try_map(self._to_publish_request),
            try_map(self._put_events),
            try_map(unbatch_uow),
            split_buffer()
        )

    def _to_publish_request_entry(self, uow: Uow[TEvent]):
        return {
            **uow,
            self.publish_request_entry_field: {
                'EventBusName': self.bus_name(uow) if callable(self.bus_name) else self.bus_name,
                'Source': self.source,
                'DetailType': uow[self.event_field]['type'],
                'Detail': json.dumps(uow[self.event_field], cls=JSONEncoder),
            } if uow.get(self.event_field) else None
        }

    def _to_publish_request(self, batch_uow: BatchUow[TEvent]):
        return {
            **batch_uow,
            self.publish_request_field: {
                'Entries': list(map(
                    lambda uow: uow[self.publish_request_entry_field],
                    filter(
                        lambda uow: uow[self.publish_request_entry_field],
                        batch_uow['batch']
                    )
                ))
            }
        }

    def _put_events(self, batch_uow: BatchUow[TEvent]):
        if len(batch_uow[self.publish_request_field]['Entries']) == 0:
            return batch_uow
        self.logger.info(batch_uow[self.publish_request_field])
        return {
            **batch_uow,
            'publish_response': self.connector.put_events(batch_uow[self.publish_request_field])
        }
