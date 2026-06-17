from modmex_lambda.logging import Logger
from modmex_lambda.connectors.eventbridge import Connector
from modmex_lambda.stream.operators.publisher import Publisher

# pylint: disable=unused-argument,too-many-arguments
def publish_to_event_bridge(
    logger=None,
    bus_name=None,
    source=None,
    event_field=None,
    publish_request_entry_field=None,
    publish_request_field=None,
    batch_size=None,
    ):
    return Publisher(
        connector=Connector(),
        logger=logger or Logger(),
        bus_name=bus_name,
        source=source,
        event_field=event_field,
        publish_request_entry_field=publish_request_entry_field,
        publish_request_field=publish_request_field,
        batch_size=batch_size,
    )
