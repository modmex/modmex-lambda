import os
from modmex_lambda.logging import Logger


def _publish_to_event_bridge(params):
    from .eventbridge import publish_to_event_bridge

    return publish_to_event_bridge(**params)


DEFAULT_OPTIONS = {
    'logger': Logger(),
    'bus_name': os.getenv('BUS_NAME'),
    'publish': _publish_to_event_bridge
}
