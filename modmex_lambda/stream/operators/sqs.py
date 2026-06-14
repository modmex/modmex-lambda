from typing import Any, Optional

from reactivex import Observable, operators as ops

from modmex_lambda.connectors.isqs import ISQSConnector
from modmex_lambda.logging import Logger
from modmex_lambda.stream.operators.ioperator import IOperator
from modmex_lambda.stream.utils.batch import to_batch_uow, unbatch_uow
from modmex_lambda.stream.utils.operators import split_buffer


class SendToSQS(IOperator):
    def __init__(
        self,
        connector: ISQSConnector,
        *,
        logger=None,
        queue_url=None,
        message_field='message',
        batch_size=10,
    ) -> None:
        self.connector = connector
        if queue_url:
            self.connector.queue_url = queue_url
        self.logger = logger or Logger()
        self.message_field = message_field
        self.batch_size = int(batch_size)

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(
            ops.buffer_with_count(self.batch_size, self.batch_size),
            ops.map(to_batch_uow),
            ops.map(self.to_input_params),
            ops.map(self.send_message_batch),
            ops.map(unbatch_uow),
            split_buffer()
        )

    def to_input_params(self, batch_uow):
        return {
            **batch_uow,
            'input_params': {
                'Entries': list(map(
                    lambda uow: uow[self.message_field],
                    filter(
                        lambda uow: self.message_field in uow,
                        batch_uow['batch']
                    )
                ))
            }
        }

    def send_message_batch(self, batch_uow):
        if len(batch_uow['input_params']['Entries']) == 0:
            return batch_uow
        self.logger.info(batch_uow['input_params'])
        return {
            **batch_uow,
            'send_message_batch_response': self.connector.send_message_batch(
                batch_uow['input_params']
            )
        }


class SQSOps:
    def __init__(self, connector: ISQSConnector) -> None:
        self.connector = connector

    def send(
        self,
        *,
        logger: Optional[Any] = None,
        queue_url=None,
        message_field='message',
        batch_size=10,
    ) -> SendToSQS:
        return SendToSQS(
            self.connector,
            logger=logger or Logger(),
            queue_url=queue_url,
            message_field=message_field,
            batch_size=batch_size,
        )
