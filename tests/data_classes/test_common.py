from __future__ import annotations

import base64

import pytest

from modmex_lambda.data_classes.common import (
    APIGatewayEventIdentity,
    BaseProxyEvent,
    BaseRequestContextV2,
    CaseInsensitiveDict,
    DictWrapper,
    RequestContextClientCert,
    _parse_cookie_string,
)


def test_case_insensitive_dict_normalizes_common_operations() -> None:
    headers = CaseInsensitiveDict({"Content-Type": "application/json"})
    headers["X-Tenant"] = "mx"

    assert headers["content-type"] == "application/json"
    assert headers.get("X-TENANT") == "mx"
    assert "x-tenant" in headers
    assert headers.pop("CONTENT-TYPE") == "application/json"
    assert headers.setdefault("X-New", "1") == "1"
    assert headers == {"x-tenant": "mx", "x-new": "1"}
    assert headers != [("x-tenant", "mx")]
    assert isinstance(hash(headers), int)

    del headers["X-Tenant"]
    assert "x-tenant" not in headers


def test_dict_wrapper_behaves_like_read_only_mapping() -> None:
    wrapper = DictWrapper({"a": 1, "b": 2})

    assert wrapper.raw_event == {"a": 1, "b": 2}
    assert wrapper["a"] == 1
    assert list(wrapper) == ["a", "b"]
    assert len(wrapper) == 2
    assert wrapper.get("missing", "fallback") == "fallback"


def test_base_proxy_event_decodes_body_query_and_cookie_helpers() -> None:
    encoded = base64.b64encode(b'{"ok": true}').decode()
    event = BaseProxyEvent(
        {
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {"ids": "1,2"},
            "multiValueQueryStringParameters": {"tag": ["a", "b"]},
            "body": encoded,
            "isBase64Encoded": True,
            "path": "/users",
            "httpMethod": "POST",
        },
    )

    assert event.headers["content-type"] == "application/json"
    assert event.resolved_headers_field["content-type"] == "application/json"
    assert event.resolved_query_string_parameters == {"ids": ["1", "2"]}
    assert event.get_query_string_value("missing", "fallback") == "fallback"
    assert event.get_multi_value_query_string_values("tag") == ["a", "b"]
    assert event.get_multi_value_query_string_values("missing") == []
    assert event.decoded_body == '{"ok": true}'
    assert event.json_body == {"ok": True}
    assert event.path == "/users"
    assert event.http_method == "POST"
    assert _parse_cookie_string("a=1; b=two; secure") == {"a": "1", "b": "two"}

    with pytest.raises(NotImplementedError):
        event.header_serializer()


def test_request_context_client_cert_identity_and_v2_authentication() -> None:
    client_cert_data = {
        "clientCertPem": "pem",
        "issuerDN": "issuer",
        "serialNumber": "serial",
        "subjectDN": "subject",
        "validity": {"notAfter": "after", "notBefore": "before"},
    }
    client_cert = RequestContextClientCert(client_cert_data)
    identity = APIGatewayEventIdentity(
        {
            "accessKey": "ak",
            "accountId": "123",
            "apiKey": "key",
            "apiKeyId": "key-id",
            "caller": "caller",
            "cognitoAuthenticationProvider": "provider",
            "cognitoAuthenticationType": "type",
            "cognitoIdentityId": "identity",
            "cognitoIdentityPoolId": "pool",
            "principalOrgId": "org",
            "sourceIp": "127.0.0.1",
            "user": "user",
            "userAgent": "pytest",
            "userArn": "arn",
            "clientCert": client_cert_data,
        },
    )

    assert client_cert.client_cert_pem == "pem"
    assert client_cert.issuer_dn == "issuer"
    assert client_cert.serial_number == "serial"
    assert client_cert.subject_dn == "subject"
    assert client_cert.validity_not_after == "after"
    assert client_cert.validity_not_before == "before"
    assert identity.access_key == "ak"
    assert identity.account_id == "123"
    assert identity.api_key == "key"
    assert identity.api_key_id == "key-id"
    assert identity.caller == "caller"
    assert identity.cognito_authentication_provider == "provider"
    assert identity.cognito_authentication_type == "type"
    assert identity.cognito_identity_id == "identity"
    assert identity.cognito_identity_pool_id == "pool"
    assert identity.principal_org_id == "org"
    assert identity.source_ip == "127.0.0.1"
    assert identity.user == "user"
    assert identity.user_agent == "pytest"
    assert identity.user_arn == "arn"
    assert identity.client_cert.client_cert_pem == "pem"
    assert APIGatewayEventIdentity({"sourceIp": "127.0.0.1"}).client_cert is None

    context = BaseRequestContextV2(
        {
            "accountId": "123",
            "apiId": "api",
            "domainName": "api.example",
            "domainPrefix": "api",
            "requestId": "req",
            "routeKey": "GET /",
            "stage": "$default",
            "time": "now",
            "timeEpoch": 1,
            "http": {
                "method": "GET",
                "path": "/",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            },
            "authentication": {"clientCert": client_cert_data},
        },
    )

    assert context.authentication.client_cert_pem == "pem"
    assert BaseRequestContextV2({"authentication": {}}).authentication is None
