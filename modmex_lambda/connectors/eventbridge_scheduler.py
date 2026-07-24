from modmex_lambda.connectors.ieventbridge_scheduler import (
    IEventBridgeSchedulerConnector,
)


class Connector(IEventBridgeSchedulerConnector):
    """Lazy adapter for the EventBridge Scheduler API."""

    def __init__(self, client=None) -> None:
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client("scheduler")
        return self._client

    def create_schedule(self, params):
        return self.client.create_schedule(**params)

    def delete_schedule(self, params):
        return self.client.delete_schedule(**params)
