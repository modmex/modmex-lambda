from __future__ import annotations

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


def base_event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "version": "1",
        "triggerSource": "PreSignUp_SignUp",
        "region": "us-east-1",
        "userPoolId": "pool-id",
        "userName": "user-name",
        "callerContext": {"awsSdkVersion": "sdk", "clientId": "client-id"},
        "request": {},
        "response": {},
    }
    event.update(overrides)
    return event


def test_base_cognito_event_exposes_common_fields_and_defaults() -> None:
    event = CognitoUserPoolEvent(
        base_event(
            request={"userAttributes": {"email": "user@example.com"}},
            response={"answer": True},
        ),
    )
    empty = CognitoUserPoolEvent({})

    assert event.version == "1"
    assert event.trigger_source == "PreSignUp_SignUp"
    assert event.region == "us-east-1"
    assert event.user_pool_id == "pool-id"
    assert event.user_name == "user-name"
    assert event.caller_context.aws_sdk_version == "sdk"
    assert event.caller_context.client_id == "client-id"
    assert event.request == {"userAttributes": {"email": "user@example.com"}}
    assert event.response == {"answer": True}

    assert empty.version == ""
    assert empty.trigger_source == ""
    assert empty.region == ""
    assert empty.user_pool_id == ""
    assert empty.user_name == ""
    assert empty.caller_context.aws_sdk_version == ""
    assert empty.caller_context.client_id == ""
    assert empty.request == {}
    assert empty.response == {}


def test_sign_up_confirmation_and_migration_events_expose_request_and_response_models() -> None:
    sign_up = PreSignUpTriggerEvent(
        base_event(
            request={
                "userAttributes": {"email": "user@example.com"},
                "validationData": {"source": "web"},
                "clientMetadata": {"tenant": "mx"},
            },
        ),
    )
    sign_up.response.auto_confirm_user = True
    sign_up.response.auto_verify_email = True
    sign_up.response.auto_verify_phone = False

    confirmation = PostConfirmationTriggerEvent(
        base_event(
            request={
                "userAttributes": {"sub": "user-id"},
                "clientMetadata": {"campaign": "launch"},
            },
        ),
    )

    migration = UserMigrationTriggerEvent(
        base_event(
            request={
                "password": "secret",
                "validationData": {"source": "legacy"},
                "clientMetadata": {"tenant": "mx"},
            },
        ),
    )
    migration.response.user_attributes = {"email": "user@example.com"}
    migration.response.final_user_status = "CONFIRMED"
    migration.response.message_action = "SUPPRESS"
    migration.response.desired_delivery_mediums = ["EMAIL"]
    migration.response.force_alias_creation = True
    migration.response.enable_sms_mfa = False

    assert sign_up.request.user_attributes == {"email": "user@example.com"}
    assert sign_up.request.validation_data == {"source": "web"}
    assert sign_up.request.client_metadata == {"tenant": "mx"}
    assert sign_up.response.auto_confirm_user is True
    assert sign_up.response.auto_verify_email is True
    assert sign_up.response.auto_verify_phone is False
    assert sign_up.raw_event["response"] == {
        "autoConfirmUser": True,
        "autoVerifyEmail": True,
        "autoVerifyPhone": False,
    }

    assert confirmation.request.user_attributes == {"sub": "user-id"}
    assert confirmation.request.client_metadata == {"campaign": "launch"}

    assert migration.request.password == "secret"
    assert migration.request.validation_data == {"source": "legacy"}
    assert migration.request.client_metadata == {"tenant": "mx"}
    assert migration.response.user_attributes == {"email": "user@example.com"}
    assert migration.response.final_user_status == "CONFIRMED"
    assert migration.response.message_action == "SUPPRESS"
    assert migration.response.desired_delivery_mediums == ["EMAIL"]
    assert migration.response.force_alias_creation is True
    assert migration.response.enable_sms_mfa is False

    empty_migration = UserMigrationTriggerEvent(base_event(response={}))
    assert empty_migration.response.final_user_status is None
    assert empty_migration.response.message_action is None
    assert empty_migration.response.force_alias_creation is None
    assert empty_migration.response.enable_sms_mfa is None


def test_message_authentication_and_token_generation_events_expose_specialized_fields() -> None:
    custom_message = CustomMessageTriggerEvent(
        base_event(
            request={
                "codeParameter": "{####}",
                "linkParameter": "{link}",
                "usernameParameter": "{username}",
                "userAttributes": {"email": "user@example.com"},
                "clientMetadata": {"locale": "es-MX"},
            },
        ),
    )
    custom_message.response.sms_message = "sms"
    custom_message.response.email_message = "email"
    custom_message.response.email_subject = "subject"

    pre_authentication = PreAuthenticationTriggerEvent(
        base_event(
            request={
                "userNotFound": True,
                "userAttributes": {"email": "user@example.com"},
                "validationData": {"ip": "127.0.0.1"},
            },
        ),
    )
    post_authentication = PostAuthenticationTriggerEvent(
        base_event(
            request={
                "newDeviceUsed": True,
                "userAttributes": {"email": "user@example.com"},
                "clientMetadata": {"tenant": "mx"},
            },
        ),
    )
    token = PreTokenGenerationTriggerEvent(
        base_event(
            request={
                "groupConfiguration": {
                    "groupsToOverride": ["admin"],
                    "iamRolesToOverride": ["role"],
                    "preferredRole": "preferred",
                },
                "userAttributes": {"sub": "user-id"},
                "clientMetadata": {"tenant": "mx"},
            },
            response={"claimsOverrideDetails": {"claimsToAddOrOverride": {"tenant": "mx"}}},
        ),
    )
    token_v2 = PreTokenGenerationV2TriggerEvent(
        base_event(
            request={"scopes": ["openid", "email"]},
            response={"claimsAndScopeOverrideDetails": {"accessTokenGeneration": {}}},
        ),
    )
    token_v3 = PreTokenGenerationV3TriggerEvent(base_event(request={"scopes": ["profile"]}))

    token.request.group_configuration.groups_to_override = ["users"]
    token.request.group_configuration.iam_roles_to_override = ["updated-role"]
    token.request.group_configuration.preferred_role = "updated-preferred"

    assert custom_message.request.code_parameter == "{####}"
    assert custom_message.request.link_parameter == "{link}"
    assert custom_message.request.username_parameter == "{username}"
    assert custom_message.request.user_attributes == {"email": "user@example.com"}
    assert custom_message.request.client_metadata == {"locale": "es-MX"}
    assert custom_message.response.sms_message == "sms"
    assert custom_message.response.email_message == "email"
    assert custom_message.response.email_subject == "subject"

    assert pre_authentication.request.user_not_found is True
    assert pre_authentication.request.user_attributes == {"email": "user@example.com"}
    assert pre_authentication.request.validation_data == {"ip": "127.0.0.1"}
    assert PreAuthenticationTriggerEvent(base_event(request={})).request.user_not_found is None
    assert post_authentication.request.new_device_used is True
    assert post_authentication.request.user_attributes == {"email": "user@example.com"}
    assert post_authentication.request.client_metadata == {"tenant": "mx"}

    assert token.request.group_configuration.groups_to_override == ["users"]
    assert token.request.group_configuration.iam_roles_to_override == ["updated-role"]
    assert token.request.group_configuration.preferred_role == "updated-preferred"
    assert token.request.user_attributes == {"sub": "user-id"}
    assert token.request.client_metadata == {"tenant": "mx"}
    assert token.response.claims_override_details == {"claimsToAddOrOverride": {"tenant": "mx"}}
    assert token_v2.request.scopes == ["openid", "email"]
    assert token_v2.response.claims_and_scope_override_details == {"accessTokenGeneration": {}}
    assert token_v3.request.scopes == ["profile"]


def test_challenge_and_sender_events_expose_request_and_response_fields() -> None:
    session = [{"challengeName": "CUSTOM_CHALLENGE", "challengeResult": True, "challengeMetadata": "meta"}]
    define = DefineAuthChallengeTriggerEvent(
        base_event(
            request={
                "userAttributes": {"sub": "user-id"},
                "userNotFound": False,
                "session": session,
                "clientMetadata": {"tenant": "mx"},
            },
        ),
    )
    define.response.challenge_name = "CUSTOM_CHALLENGE"
    define.response.fail_authentication = False
    define.response.issue_tokens = True

    create = CreateAuthChallengeTriggerEvent(
        base_event(
            request={
                "userAttributes": {"sub": "user-id"},
                "userNotFound": True,
                "challengeName": "CUSTOM_CHALLENGE",
                "session": session,
                "clientMetadata": {"tenant": "mx"},
            },
        ),
    )
    create.response.public_challenge_parameters = {"captcha": "public"}
    create.response.private_challenge_parameters = {"answer": "private"}
    create.response.challenge_metadata = "metadata"

    verify = VerifyAuthChallengeResponseTriggerEvent(
        base_event(
            request={
                "userAttributes": {"sub": "user-id"},
                "privateChallengeParameters": {"answer": "private"},
                "challengeAnswer": "private",
                "clientMetadata": {"tenant": "mx"},
                "userNotFound": False,
            },
        ),
    )
    verify.response.answer_correct = True

    email_sender = CustomEmailSenderTriggerEvent(
        base_event(
            request={
                "type": "customEmailSenderRequestV1",
                "code": "encrypted-code",
                "userAttributes": {"email": "user@example.com"},
                "clientMetadata": {"tenant": "mx"},
            },
        ),
    )
    sms_sender = CustomSMSSenderTriggerEvent(
        base_event(
            request={
                "type": "customSMSSenderRequestV1",
                "code": "encrypted-code",
                "userAttributes": {"phone_number": "+5215555555555"},
                "clientMetadata": {"tenant": "mx"},
            },
        ),
    )

    assert define.request.user_attributes == {"sub": "user-id"}
    assert define.request.user_not_found is False
    assert define.request.client_metadata == {"tenant": "mx"}
    assert define.request.session[0].challenge_name == "CUSTOM_CHALLENGE"
    assert define.request.session[0].challenge_result is True
    assert define.request.session[0].challenge_metadata == "meta"
    assert define.response.challenge_name == "CUSTOM_CHALLENGE"
    assert define.response.fail_authentication is False
    assert define.response.issue_tokens is True
    assert DefineAuthChallengeTriggerEvent(base_event(request={})).request.user_not_found is None

    assert create.request.user_attributes == {"sub": "user-id"}
    assert create.request.user_not_found is True
    assert create.request.challenge_name == "CUSTOM_CHALLENGE"
    assert create.request.session[0].challenge_name == "CUSTOM_CHALLENGE"
    assert create.request.client_metadata == {"tenant": "mx"}
    assert create.response.public_challenge_parameters == {"captcha": "public"}
    assert create.response.private_challenge_parameters == {"answer": "private"}
    assert create.response.challenge_metadata == "metadata"
    assert CreateAuthChallengeTriggerEvent(base_event(request={})).request.user_not_found is None

    assert verify.request.user_attributes == {"sub": "user-id"}
    assert verify.request.private_challenge_parameters == {"answer": "private"}
    assert verify.request.challenge_answer == "private"
    assert verify.request.client_metadata == {"tenant": "mx"}
    assert verify.request.user_not_found is False
    assert verify.response.answer_correct is True
    assert VerifyAuthChallengeResponseTriggerEvent(base_event(request={})).request.user_not_found is None

    assert email_sender.request.type == "customEmailSenderRequestV1"
    assert email_sender.request.code == "encrypted-code"
    assert email_sender.request.user_attributes == {"email": "user@example.com"}
    assert email_sender.request.client_metadata == {"tenant": "mx"}
    assert sms_sender.request.type == "customSMSSenderRequestV1"
    assert sms_sender.request.code == "encrypted-code"
    assert sms_sender.request.user_attributes == {"phone_number": "+5215555555555"}
    assert sms_sender.request.client_metadata == {"tenant": "mx"}
