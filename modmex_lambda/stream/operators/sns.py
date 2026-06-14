from uuid import uuid1

from pydash import map_
from reactivex import Observable

from modmex_lambda.connectors.isns import ISNSConnector
from modmex_lambda.stream.operators.ioperator import IOperator
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.operators import try_map


class PublishToSNS(IOperator):
    def __init__(self, connector: ISNSConnector, *, topic_arn=None, publish_message_field='sns_payload') -> None:
        self.connector = connector
        if topic_arn:
            self.connector.topic_arn = topic_arn
        self.publish_message_field = publish_message_field

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(
            try_map(faulty(self.to_input_params)),
            try_map(faulty(self.publish_batch))
        )

    def to_input_params(self, uow):
        return {
            **uow,
            'input_params': {
                'PublishBatchRequestEntries': map_(
                    uow[self.publish_message_field],
                    lambda item: {
                        'Id': str(uuid1()),
                        **item
                    }
                )
            }
        }

    def publish_batch(self, uow):
        uow['publish_response'] = self.connector.publish_batch(uow['input_params'])
        return uow


class SNSOps:
    def __init__(self, connector: ISNSConnector) -> None:
        self.connector = connector

    def publish(
        self,
        *,
        topic_arn=None,
        publish_message_field='sns_payload',
    ) -> PublishToSNS:
        return PublishToSNS(
            self.connector,
            topic_arn=topic_arn,
            publish_message_field=publish_message_field,
        )
