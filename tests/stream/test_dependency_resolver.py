from modmex_lambda.connectors.icloudwatch import ICloudWatchConnector
from modmex_lambda.connectors.idynamodb import IDynamodbConnector
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.connectors.ilambda import ILambdaConnector
from modmex_lambda.connectors.is3 import IS3Connector
from modmex_lambda.connectors.isns import ISNSConnector
from modmex_lambda.connectors.isqs import ISQSConnector
from modmex_lambda.dependencies import (
    AwsConnectorsModule,
    InjectorDependencyResolver,
    create_dependency_resolver,
)


class FakeEventBridgeConnector(IEventBridgeConnector):
    @property
    def client(self):
        return None

    def put_events(self, params):
        return {"params": params}


def test_create_dependency_resolver_uses_singleton_providers():
    resolver = create_dependency_resolver()

    first = resolver.resolve(IEventBridgeConnector)
    second = resolver.resolve(IEventBridgeConnector)

    assert first is second


def test_create_dependency_resolver_provides_default_connectors():
    resolver = create_dependency_resolver()

    assert isinstance(resolver.resolve(ICloudWatchConnector), ICloudWatchConnector)
    assert isinstance(resolver.resolve(IDynamodbConnector), IDynamodbConnector)
    assert isinstance(resolver.resolve(IEventBridgeConnector), IEventBridgeConnector)
    assert isinstance(resolver.resolve(ILambdaConnector), ILambdaConnector)
    assert isinstance(resolver.resolve(IS3Connector), IS3Connector)
    assert isinstance(resolver.resolve(ISNSConnector), ISNSConnector)
    assert isinstance(resolver.resolve(ISQSConnector), ISQSConnector)


def test_injector_dependency_resolver_can_use_custom_modules():
    from injector import Injector, Module, provider, singleton

    class AppModule(Module):
        @singleton
        @provider
        def provide_eventbridge(self) -> IEventBridgeConnector:
            return FakeEventBridgeConnector()

    resolver = InjectorDependencyResolver(
        Injector([AwsConnectorsModule(), AppModule()])
    )

    assert isinstance(resolver.resolve(IEventBridgeConnector), FakeEventBridgeConnector)
