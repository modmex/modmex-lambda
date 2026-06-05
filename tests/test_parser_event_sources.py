from __future__ import annotations

from modmex import BaseModel

from modmex_lambda.data_classes import (
    APIGatewayAuthorizerEvent,
    APIGatewayProxyEvent,
    APIGatewayProxyEventV2,
    APIGatewayWebSocketEvent,
    CognitoUserPoolEvent,
    CreateAuthChallengeTriggerEvent,
    CustomEmailSenderTriggerEvent,
    CustomMessageTriggerEvent,
    CustomSMSSenderTriggerEvent,
    DefineAuthChallengeTriggerEvent,
    DictWrapper,
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
from modmex_lambda.event_sources import event_source
from modmex_lambda.parser import event_parser, parse


class OrderEvent(BaseModel):
    order_id: str
    amount: float


class CognitoRequestModel(BaseModel):
    userAttributes: dict[str, str]


def _base_cognito_event(**overrides):
    base = {
        "version": "1",
        "triggerSource": "PreSignUp_SignUp",
        "region": "us-east-1",
        "userPoolId": "pool-1",
        "userName": "user-1",
        "callerContext": {"awsSdkVersion": "3", "clientId": "abc"},
        "request": {},
        "response": {},
    }
    base.update(overrides)
    return base


def test_parse_validates_dict_and_json_string() -> None:
    parsed_from_dict = parse(event={"order_id": "o-1", "amount": "10.5"}, model=OrderEvent)
    parsed_from_json = parse(event='{"order_id":"o-2","amount":"20.0"}', model=OrderEvent)

    assert parsed_from_dict.order_id == "o-1"
    assert parsed_from_dict.amount == 10.5
    assert parsed_from_json.order_id == "o-2"
    assert parsed_from_json.amount == 20.0


def test_event_parser_decorator_parses_event_and_preserves_context() -> None:
    seen = {}

    @event_parser(model=OrderEvent)
    def handler(event: OrderEvent, context):
        seen["event"] = event
        seen["context"] = context
        return {"order_id": event.order_id}

    context = object()
    result = handler({"order_id": "o-3", "amount": "5.5"}, context)

    assert result == {"order_id": "o-3"}
    assert isinstance(seen["event"], OrderEvent)
    assert seen["context"] is context


def test_api_gateway_proxy_event_mapping_and_json_body() -> None:
    event = APIGatewayProxyEvent(
        {
            "httpMethod": "POST",
            "path": "/items/1",
            "headers": {"x-id": "1"},
            "queryStringParameters": {"active": "true"},
            "pathParameters": {"item_id": "1"},
            "body": '{"ok": true}',
        }
    )

    assert isinstance(event, DictWrapper)
    assert event.http_method == "POST"
    assert event.path == "/items/1"
    assert event.headers["x-id"] == "1"
    assert event.query_string_parameters["active"] == "true"
    assert event.path_parameters["item_id"] == "1"
    assert event.json_body == {"ok": True}


def test_api_gateway_proxy_event_v2_fields() -> None:
    event = APIGatewayProxyEventV2(
        {
            "version": "2.0",
            "rawPath": "/v2/ping",
            "headers": {"x-v": "2"},
            "requestContext": {"stage": "$default", "http": {"method": "GET", "path": "/v2/ping"}},
            "body": '{"pong": true}',
        }
    )

    assert event.version == "2.0"
    assert event.path == "/v2/ping"
    assert event.http_method == "GET"
    assert event.headers["x-v"] == "2"
    assert event.json_body == {"pong": True}


def test_api_gateway_authorizer_event_fields() -> None:
    event = APIGatewayAuthorizerEvent(
        {
            "type": "TOKEN",
            "methodArn": "arn:aws:execute-api:region:acct:api/stage/GET/resource",
            "authorizationToken": "Bearer abc",
            "headers": {"authorization": "Bearer abc"},
            "queryStringParameters": {"debug": "1"},
            "pathParameters": {"id": "10"},
            "requestContext": {"path": "/resource"},
        }
    )

    assert event.type == "TOKEN"
    assert event.method_arn.startswith("arn:aws:execute-api")
    assert event.authorization_token == "Bearer abc"
    assert event.headers["authorization"] == "Bearer abc"
    assert event.query_string_parameters["debug"] == "1"
    assert event.path_parameters["id"] == "10"
    assert event.request_context["path"] == "/resource"


def test_api_gateway_websocket_event_fields() -> None:
    event = APIGatewayWebSocketEvent(
        {
            "requestContext": {
                "routeKey": "$default",
                "eventType": "MESSAGE",
                "connectionId": "abc123",
            },
            "body": '{"message": "hi"}',
        }
    )

    assert event.route_key == "$default"
    assert event.event_type == "MESSAGE"
    assert event.connection_id == "abc123"
    assert event.json_body == {"message": "hi"}


def test_event_source_parses_cognito_request_with_model() -> None:
    @event_source(data_class=CognitoUserPoolEvent, model=CognitoRequestModel, source="request")
    def handler(event: CognitoUserPoolEvent, _context):
        return event.parsed_request.userAttributes["email"]

    event = _base_cognito_event(
        triggerSource="PreSignUp_SignUp",
        request={"userAttributes": {"email": "user@example.com"}},
    )

    assert handler(event, object()) == "user@example.com"


def test_all_cognito_user_pool_trigger_classes_are_modeled() -> None:
    pre_sign_up = PreSignUpTriggerEvent(
        _base_cognito_event(
            triggerSource="PreSignUp_SignUp",
            request={"userAttributes": {"email": "a@b.com"}},
            response={"autoConfirmUser": False},
        )
    )
    pre_sign_up.response.auto_confirm_user = True
    assert pre_sign_up.request.user_attributes["email"] == "a@b.com"
    assert pre_sign_up.response.auto_confirm_user is True

    post_confirmation = PostConfirmationTriggerEvent(
        _base_cognito_event(
            triggerSource="PostConfirmation_ConfirmSignUp",
            request={"userAttributes": {"sub": "1"}},
        )
    )
    assert post_confirmation.request.user_attributes["sub"] == "1"

    user_migration = UserMigrationTriggerEvent(
        _base_cognito_event(
            triggerSource="UserMigration_Authentication",
            request={"password": "secret"},
            response={},
        )
    )
    user_migration.response.final_user_status = "CONFIRMED"
    assert user_migration.request.password == "secret"
    assert user_migration.response.final_user_status == "CONFIRMED"

    custom_message = CustomMessageTriggerEvent(
        _base_cognito_event(
            triggerSource="CustomMessage_SignUp",
            request={"codeParameter": "{####}", "userAttributes": {"email": "a@b.com"}},
            response={},
        )
    )
    custom_message.response.sms_message = "code {####}"
    assert custom_message.request.code_parameter == "{####}"
    assert custom_message.response.sms_message == "code {####}"

    pre_auth = PreAuthenticationTriggerEvent(
        _base_cognito_event(
            triggerSource="PreAuthentication_Authentication",
            request={"userAttributes": {"email": "a@b.com"}, "userNotFound": False},
        )
    )
    assert pre_auth.request.user_not_found is False

    post_auth = PostAuthenticationTriggerEvent(
        _base_cognito_event(
            triggerSource="PostAuthentication_Authentication",
            request={"newDeviceUsed": True, "userAttributes": {"email": "a@b.com"}},
        )
    )
    assert post_auth.request.new_device_used is True

    pre_token = PreTokenGenerationTriggerEvent(
        _base_cognito_event(
            triggerSource="TokenGeneration_Authentication",
            request={
                "groupConfiguration": {"groupsToOverride": ["admin"]},
                "userAttributes": {"sub": "1"},
            },
            response={"claimsOverrideDetails": {}},
        )
    )
    assert pre_token.request.group_configuration.groups_to_override == ["admin"]

    pre_token_v2 = PreTokenGenerationV2TriggerEvent(
        _base_cognito_event(
            triggerSource="TokenGeneration_Authentication",
            request={"scopes": ["openid"], "userAttributes": {"sub": "1"}},
            response={"claimsAndScopeOverrideDetails": {}},
        )
    )
    assert pre_token_v2.request.scopes == ["openid"]

    pre_token_v3 = PreTokenGenerationV3TriggerEvent(
        _base_cognito_event(
            triggerSource="TokenGeneration_Authentication",
            request={"scopes": ["email"]},
            response={"claimsAndScopeOverrideDetails": {}},
        )
    )
    assert pre_token_v3.request.scopes == ["email"]

    define_auth = DefineAuthChallengeTriggerEvent(
        _base_cognito_event(
            triggerSource="DefineAuthChallenge_Authentication",
            request={"session": [{"challengeName": "SRP_A", "challengeResult": True}]},
            response={},
        )
    )
    define_auth.response.issue_tokens = True
    assert define_auth.request.session[0].challenge_name == "SRP_A"
    assert define_auth.response.issue_tokens is True

    create_auth = CreateAuthChallengeTriggerEvent(
        _base_cognito_event(
            triggerSource="CreateAuthChallenge_Authentication",
            request={"challengeName": "CUSTOM_CHALLENGE", "session": []},
            response={},
        )
    )
    create_auth.response.challenge_metadata = "otp"
    assert create_auth.request.challenge_name == "CUSTOM_CHALLENGE"
    assert create_auth.response.challenge_metadata == "otp"

    verify_auth = VerifyAuthChallengeResponseTriggerEvent(
        _base_cognito_event(
            triggerSource="VerifyAuthChallengeResponse_Authentication",
            request={"challengeAnswer": "123456", "privateChallengeParameters": {}},
            response={},
        )
    )
    verify_auth.response.answer_correct = True
    assert verify_auth.request.challenge_answer == "123456"
    assert verify_auth.response.answer_correct is True

    email_sender = CustomEmailSenderTriggerEvent(
        _base_cognito_event(
            triggerSource="CustomEmailSender_SignUp",
            request={"type": "customEmailSenderRequestV1", "code": "enc", "userAttributes": {}},
        )
    )
    assert email_sender.request.type == "customEmailSenderRequestV1"

    sms_sender = CustomSMSSenderTriggerEvent(
        _base_cognito_event(
            triggerSource="CustomSMSSender_SignUp",
            request={"type": "customSMSSenderRequestV1", "code": "enc", "userAttributes": {}},
        )
    )
    assert sms_sender.request.type == "customSMSSenderRequestV1"
