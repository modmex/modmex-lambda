import os
from modmex_lambda.logging import Logger
from modmex_lambda.connectors.sqs import Connector
from modmex_lambda.stream.operators.sqs import SendToSQS


def send_to_sqs(
    logger=None,
    queue_url = os.getenv('QUEUE_URL'),
    message_field = 'message',
    batch_size=os.getenv('SQS_BATCH_SIZE') or os.getenv('BATCH_SIZE') or 10
    ):
    return SendToSQS(
        Connector(queue_url),
        logger=logger or Logger(),
        queue_url=queue_url,
        message_field=message_field,
        batch_size=batch_size,
    )
