"""Injector module with default AWS connector bindings."""

from __future__ import annotations

from injector import Module, provider, singleton

from modmex_lambda.connectors.icloudwatch import ICloudWatchConnector
from modmex_lambda.connectors.idynamodb import IDynamodbConnector
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.connectors.ilambda import ILambdaConnector
from modmex_lambda.connectors.is3 import IS3Connector
from modmex_lambda.connectors.isns import ISNSConnector
from modmex_lambda.connectors.isqs import ISQSConnector


class AwsConnectorsModule(Module):
    @singleton
    @provider
    def provide_dynamodb(self) -> IDynamodbConnector:
        from modmex_lambda.connectors.dynamodb import Connector

        return Connector()

    @singleton
    @provider
    def provide_cloudwatch(self) -> ICloudWatchConnector:
        from modmex_lambda.connectors.cloudwatch import Connector

        return Connector()

    @singleton
    @provider
    def provide_eventbridge(self) -> IEventBridgeConnector:
        from modmex_lambda.connectors.eventbridge import Connector

        return Connector()

    @singleton
    @provider
    def provide_lambda(self) -> ILambdaConnector:
        from modmex_lambda.connectors.lambda_ import Connector

        return Connector()

    @singleton
    @provider
    def provide_s3(self) -> IS3Connector:
        from modmex_lambda.connectors.s3 import Connector

        return Connector(None)

    @singleton
    @provider
    def provide_sns(self) -> ISNSConnector:
        from modmex_lambda.connectors.sns import Connector

        return Connector()

    @singleton
    @provider
    def provide_sqs(self) -> ISQSConnector:
        from modmex_lambda.connectors.sqs import Connector

        return Connector()


__all__ = ["AwsConnectorsModule"]
