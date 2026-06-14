from modmex_lambda.connectors.sns import Connector
from modmex_lambda.stream.operators.sns import PublishToSNS

def publish_to_sns(
    connector: Connector,
    publish_message_field='sns_payload',
):
    return PublishToSNS(
        connector,
        publish_message_field=publish_message_field,
    )
