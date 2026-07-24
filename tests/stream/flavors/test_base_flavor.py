from expects import equal, expect

from modmex_lambda.connectors.icloudwatch import ICloudWatchConnector
from modmex_lambda.connectors.idynamodb import IDynamodbConnector
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.connectors.ieventbridge_scheduler import (
    IEventBridgeSchedulerConnector,
)
from modmex_lambda.connectors.ilambda import ILambdaConnector
from modmex_lambda.connectors.is3 import IS3Connector
from modmex_lambda.connectors.isns import ISNSConnector
from modmex_lambda.connectors.isqs import ISQSConnector
from modmex_lambda.stream.flavors.base_flavor import BaseFlavor
from modmex_lambda.stream.operators.cloudwatch import CloudWatchOps
from modmex_lambda.stream.operators.dynamodb import DynamoDBOps
from modmex_lambda.stream.operators.lambda_ import LambdaOps
from modmex_lambda.stream.operators.publisher import Publisher
from modmex_lambda.stream.operators.s3 import S3Ops
from modmex_lambda.stream.operators.sns import SNSOps
from modmex_lambda.stream.operators.sqs import SQSOps
from modmex_lambda.stream.operators.scheduler import SchedulerOps


class Resolver:
    def __init__(self):
        self.values = {
            ICloudWatchConnector: object(),
            IDynamodbConnector: object(),
            IEventBridgeConnector: object(),
            IEventBridgeSchedulerConnector: object(),
            ILambdaConnector: object(),
            IS3Connector: object(),
            ISNSConnector: object(),
            ISQSConnector: object(),
        }

    def resolve(self, dependency):
        return self.values[dependency]


class ConcreteFlavor(BaseFlavor):
    @property
    def id(self):
        return "test"

    def __call__(self, source):
        return source


def test_base_flavor_lazily_creates_ops_and_publisher():
    flavor = ConcreteFlavor(dependency_resolver=Resolver())

    expect(isinstance(flavor.cloudwatch_ops, CloudWatchOps)).to(equal(True))
    expect(flavor.cloudwatch_ops).to(equal(flavor.cloudwatch_ops))
    expect(isinstance(flavor.dynamodb_ops, DynamoDBOps)).to(equal(True))
    expect(isinstance(flavor.lambda_ops, LambdaOps)).to(equal(True))
    expect(isinstance(flavor.s3_ops, S3Ops)).to(equal(True))
    expect(isinstance(flavor.sns_ops, SNSOps)).to(equal(True))
    expect(isinstance(flavor.sqs_ops, SQSOps)).to(equal(True))
    expect(isinstance(flavor.scheduler_ops, SchedulerOps)).to(equal(True))
    expect(isinstance(flavor.publisher, Publisher)).to(equal(True))
    expect(flavor.publisher).to(equal(flavor.publisher))


def test_base_flavor_bind_keeps_existing_resolver():
    original = Resolver()
    replacement = Resolver()
    flavor = ConcreteFlavor(dependency_resolver=original)

    flavor.bind(replacement)

    expect(flavor.dependency_resolver).to(equal(original))


def test_base_flavor_creates_fresh_default_logger_per_instance():
    first = ConcreteFlavor()
    second = ConcreteFlavor()

    expect(first.logger is second.logger).to(equal(False))
