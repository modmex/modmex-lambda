"""Cognito User Pool trigger event data classes."""

from __future__ import annotations

from typing import Any

from modmex_lambda.data_classes.common import DictWrapper


class CallerContext(DictWrapper):
    @property
    def aws_sdk_version(self) -> str:
        return str(self.get("awsSdkVersion") or "")

    @property
    def client_id(self) -> str:
        return str(self.get("clientId") or "")


class BaseTriggerEvent(DictWrapper):
    @property
    def version(self) -> str:
        return str(self.get("version") or "")

    @property
    def trigger_source(self) -> str:
        return str(self.get("triggerSource") or "")

    @property
    def region(self) -> str:
        return str(self.get("region") or "")

    @property
    def user_pool_id(self) -> str:
        return str(self.get("userPoolId") or "")

    @property
    def user_name(self) -> str:
        return str(self.get("userName") or "")

    @property
    def caller_context(self) -> CallerContext:
        return CallerContext(self.get("callerContext") or {})

    @property
    def request(self) -> dict[str, Any]:
        return dict(self.get("request") or {})

    @property
    def response(self) -> dict[str, Any]:
        return dict(self.get("response") or {})


class PreSignUpTriggerEventRequest(DictWrapper):
    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def validation_data(self) -> dict[str, Any]:
        return dict(self.get("validationData") or {})

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})


class PreSignUpTriggerEventResponse(DictWrapper):
    @property
    def auto_confirm_user(self) -> bool:
        return bool(self.get("autoConfirmUser"))

    @auto_confirm_user.setter
    def auto_confirm_user(self, value: bool) -> None:
        self._data["autoConfirmUser"] = value

    @property
    def auto_verify_email(self) -> bool:
        return bool(self.get("autoVerifyEmail"))

    @auto_verify_email.setter
    def auto_verify_email(self, value: bool) -> None:
        self._data["autoVerifyEmail"] = value

    @property
    def auto_verify_phone(self) -> bool:
        return bool(self.get("autoVerifyPhone"))

    @auto_verify_phone.setter
    def auto_verify_phone(self, value: bool) -> None:
        self._data["autoVerifyPhone"] = value


class PreSignUpTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> PreSignUpTriggerEventRequest:
        return PreSignUpTriggerEventRequest(self._data.setdefault("request", {}))

    @property
    def response(self) -> PreSignUpTriggerEventResponse:
        return PreSignUpTriggerEventResponse(self._data.setdefault("response", {}))


class PostConfirmationTriggerEventRequest(DictWrapper):
    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})


class PostConfirmationTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> PostConfirmationTriggerEventRequest:
        return PostConfirmationTriggerEventRequest(self.get("request") or {})


class UserMigrationTriggerEventRequest(DictWrapper):
    @property
    def password(self) -> str:
        return str(self.get("password") or "")

    @property
    def validation_data(self) -> dict[str, Any]:
        return dict(self.get("validationData") or {})

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})


class UserMigrationTriggerEventResponse(DictWrapper):
    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @user_attributes.setter
    def user_attributes(self, value: dict[str, Any]) -> None:
        self._data["userAttributes"] = value

    @property
    def final_user_status(self) -> str | None:
        value = self.get("finalUserStatus")
        return None if value is None else str(value)

    @final_user_status.setter
    def final_user_status(self, value: str) -> None:
        self._data["finalUserStatus"] = value

    @property
    def message_action(self) -> str | None:
        value = self.get("messageAction")
        return None if value is None else str(value)

    @message_action.setter
    def message_action(self, value: str) -> None:
        self._data["messageAction"] = value

    @property
    def desired_delivery_mediums(self) -> list[str]:
        return [str(item) for item in (self.get("desiredDeliveryMediums") or [])]

    @desired_delivery_mediums.setter
    def desired_delivery_mediums(self, value: list[str]) -> None:
        self._data["desiredDeliveryMediums"] = value

    @property
    def force_alias_creation(self) -> bool | None:
        value = self.get("forceAliasCreation")
        return None if value is None else bool(value)

    @force_alias_creation.setter
    def force_alias_creation(self, value: bool) -> None:
        self._data["forceAliasCreation"] = value

    @property
    def enable_sms_mfa(self) -> bool | None:
        value = self.get("enableSMSMFA")
        return None if value is None else bool(value)

    @enable_sms_mfa.setter
    def enable_sms_mfa(self, value: bool) -> None:
        self._data["enableSMSMFA"] = value


class UserMigrationTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> UserMigrationTriggerEventRequest:
        return UserMigrationTriggerEventRequest(self.get("request") or {})

    @property
    def response(self) -> UserMigrationTriggerEventResponse:
        return UserMigrationTriggerEventResponse(self._data.setdefault("response", {}))


class CustomMessageTriggerEventRequest(DictWrapper):
    @property
    def code_parameter(self) -> str:
        return str(self.get("codeParameter") or "")

    @property
    def link_parameter(self) -> str:
        return str(self.get("linkParameter") or "")

    @property
    def username_parameter(self) -> str:
        return str(self.get("usernameParameter") or "")

    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})


class CustomMessageTriggerEventResponse(DictWrapper):
    @property
    def sms_message(self) -> str:
        return str(self.get("smsMessage") or "")

    @sms_message.setter
    def sms_message(self, value: str) -> None:
        self._data["smsMessage"] = value

    @property
    def email_message(self) -> str:
        return str(self.get("emailMessage") or "")

    @email_message.setter
    def email_message(self, value: str) -> None:
        self._data["emailMessage"] = value

    @property
    def email_subject(self) -> str:
        return str(self.get("emailSubject") or "")

    @email_subject.setter
    def email_subject(self, value: str) -> None:
        self._data["emailSubject"] = value


class CustomMessageTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> CustomMessageTriggerEventRequest:
        return CustomMessageTriggerEventRequest(self.get("request") or {})

    @property
    def response(self) -> CustomMessageTriggerEventResponse:
        return CustomMessageTriggerEventResponse(self._data.setdefault("response", {}))


class PreAuthenticationTriggerEventRequest(DictWrapper):
    @property
    def user_not_found(self) -> bool | None:
        value = self.get("userNotFound")
        return None if value is None else bool(value)

    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def validation_data(self) -> dict[str, Any]:
        return dict(self.get("validationData") or {})


class PreAuthenticationTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> PreAuthenticationTriggerEventRequest:
        return PreAuthenticationTriggerEventRequest(self.get("request") or {})


class PostAuthenticationTriggerEventRequest(DictWrapper):
    @property
    def new_device_used(self) -> bool:
        return bool(self.get("newDeviceUsed"))

    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})


class PostAuthenticationTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> PostAuthenticationTriggerEventRequest:
        return PostAuthenticationTriggerEventRequest(self.get("request") or {})


class GroupOverrideDetails(DictWrapper):
    @property
    def groups_to_override(self) -> list[str]:
        return [str(item) for item in (self.get("groupsToOverride") or [])]

    @groups_to_override.setter
    def groups_to_override(self, value: list[str]) -> None:
        self._data["groupsToOverride"] = value

    @property
    def iam_roles_to_override(self) -> list[str]:
        return [str(item) for item in (self.get("iamRolesToOverride") or [])]

    @iam_roles_to_override.setter
    def iam_roles_to_override(self, value: list[str]) -> None:
        self._data["iamRolesToOverride"] = value

    @property
    def preferred_role(self) -> str:
        return str(self.get("preferredRole") or "")

    @preferred_role.setter
    def preferred_role(self, value: str) -> None:
        self._data["preferredRole"] = value


class PreTokenGenerationTriggerEventRequest(DictWrapper):
    @property
    def group_configuration(self) -> GroupOverrideDetails:
        return GroupOverrideDetails(self.get("groupConfiguration") or {})

    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})


class PreTokenGenerationTriggerV2EventRequest(PreTokenGenerationTriggerEventRequest):
    @property
    def scopes(self) -> list[str]:
        return [str(item) for item in (self.get("scopes") or [])]


class PreTokenGenerationTriggerEventResponse(DictWrapper):
    @property
    def claims_override_details(self) -> dict[str, Any]:
        return dict(self.get("claimsOverrideDetails") or {})


class PreTokenGenerationTriggerV2EventResponse(DictWrapper):
    @property
    def claims_and_scope_override_details(self) -> dict[str, Any]:
        return dict(self.get("claimsAndScopeOverrideDetails") or {})


class PreTokenGenerationTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> PreTokenGenerationTriggerEventRequest:
        return PreTokenGenerationTriggerEventRequest(self.get("request") or {})

    @property
    def response(self) -> PreTokenGenerationTriggerEventResponse:
        return PreTokenGenerationTriggerEventResponse(self._data.setdefault("response", {}))


class PreTokenGenerationV2TriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> PreTokenGenerationTriggerV2EventRequest:
        return PreTokenGenerationTriggerV2EventRequest(self.get("request") or {})

    @property
    def response(self) -> PreTokenGenerationTriggerV2EventResponse:
        return PreTokenGenerationTriggerV2EventResponse(self._data.setdefault("response", {}))


class PreTokenGenerationV3TriggerEvent(PreTokenGenerationV2TriggerEvent):
    """Alias for V3 payloads, which currently follow the V2 shape."""


class ChallengeResult(DictWrapper):
    @property
    def challenge_name(self) -> str:
        return str(self.get("challengeName") or "")

    @property
    def challenge_result(self) -> bool:
        return bool(self.get("challengeResult"))

    @property
    def challenge_metadata(self) -> str:
        return str(self.get("challengeMetadata") or "")


class DefineAuthChallengeTriggerEventRequest(DictWrapper):
    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def user_not_found(self) -> bool | None:
        value = self.get("userNotFound")
        return None if value is None else bool(value)

    @property
    def session(self) -> list[ChallengeResult]:
        return [ChallengeResult(item) for item in (self.get("session") or [])]

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})


class DefineAuthChallengeTriggerEventResponse(DictWrapper):
    @property
    def challenge_name(self) -> str:
        return str(self.get("challengeName") or "")

    @challenge_name.setter
    def challenge_name(self, value: str) -> None:
        self._data["challengeName"] = value

    @property
    def fail_authentication(self) -> bool:
        return bool(self.get("failAuthentication"))

    @fail_authentication.setter
    def fail_authentication(self, value: bool) -> None:
        self._data["failAuthentication"] = value

    @property
    def issue_tokens(self) -> bool:
        return bool(self.get("issueTokens"))

    @issue_tokens.setter
    def issue_tokens(self, value: bool) -> None:
        self._data["issueTokens"] = value


class DefineAuthChallengeTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> DefineAuthChallengeTriggerEventRequest:
        return DefineAuthChallengeTriggerEventRequest(self.get("request") or {})

    @property
    def response(self) -> DefineAuthChallengeTriggerEventResponse:
        return DefineAuthChallengeTriggerEventResponse(self._data.setdefault("response", {}))


class CreateAuthChallengeTriggerEventRequest(DictWrapper):
    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def user_not_found(self) -> bool | None:
        value = self.get("userNotFound")
        return None if value is None else bool(value)

    @property
    def challenge_name(self) -> str:
        return str(self.get("challengeName") or "")

    @property
    def session(self) -> list[ChallengeResult]:
        return [ChallengeResult(item) for item in (self.get("session") or [])]

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})


class CreateAuthChallengeTriggerEventResponse(DictWrapper):
    @property
    def public_challenge_parameters(self) -> dict[str, Any]:
        return dict(self.get("publicChallengeParameters") or {})

    @public_challenge_parameters.setter
    def public_challenge_parameters(self, value: dict[str, Any]) -> None:
        self._data["publicChallengeParameters"] = value

    @property
    def private_challenge_parameters(self) -> dict[str, Any]:
        return dict(self.get("privateChallengeParameters") or {})

    @private_challenge_parameters.setter
    def private_challenge_parameters(self, value: dict[str, Any]) -> None:
        self._data["privateChallengeParameters"] = value

    @property
    def challenge_metadata(self) -> str:
        return str(self.get("challengeMetadata") or "")

    @challenge_metadata.setter
    def challenge_metadata(self, value: str) -> None:
        self._data["challengeMetadata"] = value


class CreateAuthChallengeTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> CreateAuthChallengeTriggerEventRequest:
        return CreateAuthChallengeTriggerEventRequest(self.get("request") or {})

    @property
    def response(self) -> CreateAuthChallengeTriggerEventResponse:
        return CreateAuthChallengeTriggerEventResponse(self._data.setdefault("response", {}))


class VerifyAuthChallengeResponseTriggerEventRequest(DictWrapper):
    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def private_challenge_parameters(self) -> dict[str, Any]:
        return dict(self.get("privateChallengeParameters") or {})

    @property
    def challenge_answer(self) -> Any:
        return self.get("challengeAnswer")

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})

    @property
    def user_not_found(self) -> bool | None:
        value = self.get("userNotFound")
        return None if value is None else bool(value)


class VerifyAuthChallengeResponseTriggerEventResponse(DictWrapper):
    @property
    def answer_correct(self) -> bool:
        return bool(self.get("answerCorrect"))

    @answer_correct.setter
    def answer_correct(self, value: bool) -> None:
        self._data["answerCorrect"] = value


class VerifyAuthChallengeResponseTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> VerifyAuthChallengeResponseTriggerEventRequest:
        return VerifyAuthChallengeResponseTriggerEventRequest(self.get("request") or {})

    @property
    def response(self) -> VerifyAuthChallengeResponseTriggerEventResponse:
        return VerifyAuthChallengeResponseTriggerEventResponse(self._data.setdefault("response", {}))


class CustomEmailSenderTriggerEventRequest(DictWrapper):
    @property
    def type(self) -> str:
        return str(self.get("type") or "")

    @property
    def code(self) -> str:
        return str(self.get("code") or "")

    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})


class CustomEmailSenderTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> CustomEmailSenderTriggerEventRequest:
        return CustomEmailSenderTriggerEventRequest(self.get("request") or {})


class CustomSMSSenderTriggerEventRequest(DictWrapper):
    @property
    def type(self) -> str:
        return str(self.get("type") or "")

    @property
    def code(self) -> str:
        return str(self.get("code") or "")

    @property
    def user_attributes(self) -> dict[str, Any]:
        return dict(self.get("userAttributes") or {})

    @property
    def client_metadata(self) -> dict[str, Any]:
        return dict(self.get("clientMetadata") or {})


class CustomSMSSenderTriggerEvent(BaseTriggerEvent):
    @property
    def request(self) -> CustomSMSSenderTriggerEventRequest:
        return CustomSMSSenderTriggerEventRequest(self.get("request") or {})


class CognitoUserPoolEvent(BaseTriggerEvent):
    """Generic Cognito User Pool event wrapper kept for compatibility."""
