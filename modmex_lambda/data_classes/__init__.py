from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modmex_lambda.data_classes.api_gateway_authorizer_event import APIGatewayAuthorizerEvent
    from modmex_lambda.data_classes.api_gateway_proxy_event import APIGatewayProxyEvent, APIGatewayProxyEventV2
    from modmex_lambda.data_classes.api_gateway_websocket_event import APIGatewayWebSocketEvent
    from modmex_lambda.data_classes.cognito_user_pool_event import (
        CognitoUserPoolEvent,
        CreateAuthChallengeTriggerEvent,
        CustomEmailSenderTriggerEvent,
        CustomMessageTriggerEvent,
        CustomSMSSenderTriggerEvent,
        DefineAuthChallengeTriggerEvent,
        PostAuthenticationTriggerEvent,
        PostConfirmationTriggerEvent,
        PreAuthenticationTriggerEvent,
        PreSignUpTriggerEvent,
        PreTokenGenerationTriggerEvent,
        PreTokenGenerationV2TriggerEvent,
        PreTokenGenerationV3TriggerEvent,
        UserMigrationTriggerEvent,
        VerifyAuthChallengeResponseTriggerEvent,
    )
    from modmex_lambda.data_classes.common import DictWrapper


_EXPORTS = {
    "DictWrapper": ("modmex_lambda.data_classes.common", "DictWrapper"),
    "APIGatewayProxyEvent": ("modmex_lambda.data_classes.api_gateway_proxy_event", "APIGatewayProxyEvent"),
    "APIGatewayProxyEventV2": ("modmex_lambda.data_classes.api_gateway_proxy_event", "APIGatewayProxyEventV2"),
    "APIGatewayRestEvent": ("modmex_lambda.data_classes.api_gateway_proxy_event", "APIGatewayProxyEvent"),
    "APIGatewayHttpEvent": ("modmex_lambda.data_classes.api_gateway_proxy_event", "APIGatewayProxyEventV2"),
    "APIGatewayAuthorizerEvent": (
        "modmex_lambda.data_classes.api_gateway_authorizer_event",
        "APIGatewayAuthorizerEvent",
    ),
    "APIGatewayWebSocketEvent": (
        "modmex_lambda.data_classes.api_gateway_websocket_event",
        "APIGatewayWebSocketEvent",
    ),
    "CognitoUserPoolEvent": ("modmex_lambda.data_classes.cognito_user_pool_event", "CognitoUserPoolEvent"),
    "PreSignUpTriggerEvent": ("modmex_lambda.data_classes.cognito_user_pool_event", "PreSignUpTriggerEvent"),
    "PostConfirmationTriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "PostConfirmationTriggerEvent",
    ),
    "UserMigrationTriggerEvent": ("modmex_lambda.data_classes.cognito_user_pool_event", "UserMigrationTriggerEvent"),
    "CustomMessageTriggerEvent": ("modmex_lambda.data_classes.cognito_user_pool_event", "CustomMessageTriggerEvent"),
    "PreAuthenticationTriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "PreAuthenticationTriggerEvent",
    ),
    "PostAuthenticationTriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "PostAuthenticationTriggerEvent",
    ),
    "PreTokenGenerationTriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "PreTokenGenerationTriggerEvent",
    ),
    "PreTokenGenerationV2TriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "PreTokenGenerationV2TriggerEvent",
    ),
    "PreTokenGenerationV3TriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "PreTokenGenerationV3TriggerEvent",
    ),
    "DefineAuthChallengeTriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "DefineAuthChallengeTriggerEvent",
    ),
    "CreateAuthChallengeTriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "CreateAuthChallengeTriggerEvent",
    ),
    "VerifyAuthChallengeResponseTriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "VerifyAuthChallengeResponseTriggerEvent",
    ),
    "CustomEmailSenderTriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "CustomEmailSenderTriggerEvent",
    ),
    "CustomSMSSenderTriggerEvent": (
        "modmex_lambda.data_classes.cognito_user_pool_event",
        "CustomSMSSenderTriggerEvent",
    ),
}

__all__ = [
    "DictWrapper",
    "APIGatewayProxyEvent",
    "APIGatewayProxyEventV2",
    "APIGatewayRestEvent",
    "APIGatewayHttpEvent",
    "APIGatewayAuthorizerEvent",
    "APIGatewayWebSocketEvent",
    "CognitoUserPoolEvent",
    "PreSignUpTriggerEvent",
    "PostConfirmationTriggerEvent",
    "UserMigrationTriggerEvent",
    "CustomMessageTriggerEvent",
    "PreAuthenticationTriggerEvent",
    "PostAuthenticationTriggerEvent",
    "PreTokenGenerationTriggerEvent",
    "PreTokenGenerationV2TriggerEvent",
    "PreTokenGenerationV3TriggerEvent",
    "DefineAuthChallengeTriggerEvent",
    "CreateAuthChallengeTriggerEvent",
    "VerifyAuthChallengeResponseTriggerEvent",
    "CustomEmailSenderTriggerEvent",
    "CustomSMSSenderTriggerEvent",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr = target
    value = getattr(import_module(module_name), attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals().keys(), *__all__])
