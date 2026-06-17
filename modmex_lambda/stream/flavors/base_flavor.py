from typing import TYPE_CHECKING, Any, Generic, Optional, Type, TypeVar

from modmex_lambda.connectors.icloudwatch import ICloudWatchConnector
from modmex_lambda.connectors.idynamodb import IDynamodbConnector
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.connectors.ilambda import ILambdaConnector
from modmex_lambda.connectors.is3 import IS3Connector
from modmex_lambda.connectors.isns import ISNSConnector
from modmex_lambda.connectors.isqs import ISQSConnector
from modmex_lambda.dependencies import (
    DependencyResolver,
    default_dependency_resolver,
)
from modmex_lambda.logging import Logger
from modmex_lambda.stream.flavors.iflavor import IFlavor
from modmex_lambda.stream.operators.publisher import Publisher, PublisherOptions
from modmex_lambda.stream.utils.contracts import Event


if TYPE_CHECKING:
    from modmex_lambda.stream.operators.cloudwatch import CloudWatchOps
    from modmex_lambda.stream.operators.dynamodb import DynamoDBOps
    from modmex_lambda.stream.operators.lambda_ import LambdaOps
    from modmex_lambda.stream.operators.s3 import S3Ops
    from modmex_lambda.stream.operators.sns import SNSOps
    from modmex_lambda.stream.operators.sqs import SQSOps


TEvent = TypeVar("TEvent", bound=Event)


class BaseFlavor(Generic[TEvent], IFlavor):

    def __init__(
        self,
        *,
        logger: Optional[Any] = None,
        connector: Optional[IEventBridgeConnector] = None,
        dependency_resolver: Optional[DependencyResolver] = None,
        publisher_options: Optional[PublisherOptions] = None,
    ) -> None:
        self.logger = logger or Logger()
        self.connector = connector
        self.dependency_resolver = dependency_resolver
        self.publisher_options = publisher_options or {}
        self._publisher: Optional[Publisher[TEvent]] = None
        self._cloudwatch_ops: Optional["CloudWatchOps"] = None
        self._dynamodb_ops: Optional["DynamoDBOps"] = None
        self._lambda_ops: Optional["LambdaOps"] = None
        self._s3_ops: Optional["S3Ops"] = None
        self._sns_ops: Optional["SNSOps"] = None
        self._sqs_ops: Optional["SQSOps"] = None

    def bind(self, dependency_resolver: DependencyResolver) -> "BaseFlavor[TEvent]":
        if self.dependency_resolver is None:
            self.dependency_resolver = dependency_resolver
        return self

    def resolve(self, dependency: Type[Any]) -> Any:
        resolver = self.dependency_resolver or default_dependency_resolver()
        return resolver.resolve(dependency)

    @property
    def cloudwatch_ops(self) -> "CloudWatchOps":
        if self._cloudwatch_ops is None:
            from modmex_lambda.stream.operators.cloudwatch import CloudWatchOps

            self._cloudwatch_ops = CloudWatchOps(
                self.resolve(ICloudWatchConnector)
            )
        return self._cloudwatch_ops

    @property
    def dynamodb_ops(self) -> "DynamoDBOps":
        if self._dynamodb_ops is None:
            from modmex_lambda.stream.operators.dynamodb import DynamoDBOps

            self._dynamodb_ops = DynamoDBOps(
                self.resolve(IDynamodbConnector)
            )
        return self._dynamodb_ops

    @property
    def lambda_ops(self) -> "LambdaOps":
        if self._lambda_ops is None:
            from modmex_lambda.stream.operators.lambda_ import LambdaOps

            self._lambda_ops = LambdaOps(
                self.resolve(ILambdaConnector)
            )
        return self._lambda_ops

    @property
    def s3_ops(self) -> "S3Ops":
        if self._s3_ops is None:
            from modmex_lambda.stream.operators.s3 import S3Ops

            self._s3_ops = S3Ops(
                self.resolve(IS3Connector)
            )
        return self._s3_ops

    @property
    def sns_ops(self) -> "SNSOps":
        if self._sns_ops is None:
            from modmex_lambda.stream.operators.sns import SNSOps

            self._sns_ops = SNSOps(
                self.resolve(ISNSConnector)
            )
        return self._sns_ops

    @property
    def sqs_ops(self) -> "SQSOps":
        if self._sqs_ops is None:
            from modmex_lambda.stream.operators.sqs import SQSOps

            self._sqs_ops = SQSOps(
                self.resolve(ISQSConnector)
            )
        return self._sqs_ops

    @property
    def publisher(self) -> Publisher[TEvent]:
        if self._publisher is None:
            options = self.publisher_options
            self._publisher = Publisher[TEvent](
                connector=self.connector or self.resolve(IEventBridgeConnector),
                logger=self.logger,
                bus_name=options.get("bus_name"),
                source=options.get("source"),
                event_field=options.get("event_field"),
                publish_request_entry_field=options.get("publish_request_entry_field"),
                publish_request_field=options.get("publish_request_field"),
                batch_size=options.get("batch_size"),
            )
        return self._publisher


Flavor = BaseFlavor
