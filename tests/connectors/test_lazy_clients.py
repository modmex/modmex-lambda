from expects import equal, expect
from modmex_lambda.connectors.cloudwatch import Connector as CloudwatchConnector
from modmex_lambda.connectors.dynamodb import Connector as DynamoConnector
from modmex_lambda.connectors.eventbridge import Connector as EventbridgeConnector
from modmex_lambda.connectors.eventbridge_scheduler import (
    Connector as EventbridgeSchedulerConnector,
)
from modmex_lambda.connectors.lambda_ import Connector as LambdaConnector
from modmex_lambda.connectors.s3 import Connector as S3Connector
from modmex_lambda.connectors.sns import Connector as SnsConnector
from modmex_lambda.connectors.sqs import Connector as SqsConnector


class Boto:
    def __init__(self):
        self.client_calls = []
        self.resource_calls = []
        self.sessions = []

    def client(self, *args, **kwargs):
        self.client_calls.append((args, kwargs))
        return {
            'client': args[0],
            'kwargs': kwargs,
        }

    def resource(self, *args, **kwargs):
        self.resource_calls.append((args, kwargs))
        return {
            'resource': args[0],
            'kwargs': kwargs,
        }

    def Session(self):  # pylint: disable=invalid-name
        session = {
            'session': True,
        }
        self.sessions.append(session)
        return session


def test_lazy_boto_clients(monkeypatch):
    import boto3

    boto = Boto()
    monkeypatch.setattr(boto3, 'client', boto.client)
    monkeypatch.setattr(boto3, 'resource', boto.resource)
    monkeypatch.setattr(boto3, 'Session', boto.Session)

    expect(CloudwatchConnector().client).to(equal({'client': 'cloudwatch', 'kwargs': {}}))
    expect(EventbridgeConnector().client).to(equal({'client': 'events', 'kwargs': {}}))
    expect(EventbridgeSchedulerConnector().client).to(equal({
        'client': 'scheduler', 'kwargs': {}
    }))
    expect(LambdaConnector().client).to(equal({'client': 'lambda', 'kwargs': {}}))
    expect(S3Connector('bucket').client).to(equal({'client': 's3', 'kwargs': {}}))
    expect(SqsConnector('queue').client).to(equal({'client': 'sqs', 'kwargs': {}}))
    expect(SnsConnector('arn:aws:sns:us-east-1:123:topic').client).to(equal({
        'client': 'sns',
        'kwargs': {
            'region_name': 'us-east-1',
        },
    }))
    expect(DynamoConnector('table').client).to(equal({'client': 'dynamodb', 'kwargs': {}}))

    expect(boto.client_calls).to(equal([
        (('cloudwatch',), {}),
        (('events',), {}),
        (('scheduler',), {}),
        (('lambda',), {}),
        (('s3',), {}),
        (('sqs',), {}),
        (('sns',), {
            'region_name': 'us-east-1',
        }),
        (('dynamodb',), {}),
    ]))
    expect(boto.resource_calls).to(equal([]))
    expect(boto.sessions).to(equal([]))
