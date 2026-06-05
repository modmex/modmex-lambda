from __future__ import annotations

import base64
import json
from functools import cached_property
from collections.abc import Callable, Iterator, Mapping
from typing import Any, overload
from modmex_lambda.shared.headers_serializer import BaseHeadersSerializer


def _parse_cookie_string(cookie_string: str) -> dict[str, str]:
    """Parse a cookie string (``key=value; key2=value2``) into a dict."""
    cookies: dict[str, str] = {}
    for segment in cookie_string.split(";"):
        stripped = segment.strip()
        if "=" in stripped:
            name, _, value = stripped.partition("=")
            cookies[name.strip()] = value.strip()
    return cookies


class CaseInsensitiveDict(dict):
    """Case insensitive dict implementation. Assumes string keys only."""

    def __init__(self, data=None, **kwargs):
        super().__init__()
        self.update(data, **kwargs)

    def get(self, k, default=None):
        return super().get(k.lower(), default)

    def pop(self, k, *args):
        return super().pop(k.lower(), *args)

    def setdefault(self, k, default=None):
        return super().setdefault(k.lower(), default)

    def update(self, data=None, **kwargs):
        if data is not None:
            if isinstance(data, Mapping):
                data = data.items()
            super().update((k.lower(), v) for k, v in data)
        super().update((k.lower(), v) for k, v in kwargs)

    def __contains__(self, k):
        return super().__contains__(k.lower())

    def __delitem__(self, k):
        super().__delitem__(k.lower())

    def __eq__(self, other):
        if not isinstance(other, Mapping):
            return False
        if not isinstance(other, CaseInsensitiveDict):
            other = CaseInsensitiveDict(other)
        return super().__eq__(other)

    def __getitem__(self, k):
        return super().__getitem__(k.lower())

    def __setitem__(self, k, v):
        super().__setitem__(k.lower(), v)

    def __hash__(self):
        # Convert the dictionary to a frozenset of tuples (key, value)
        # where all keys are lowercase
        items = frozenset((k.lower(), v) for k, v in self.items())
        return hash(items)
    

class DictWrapper(Mapping[str, Any]):
    """read-only dict wrapper with helper accessors."""

    def __init__(self, data: dict[str, Any], json_deserializer: Callable[[str], Any] | None = None) -> None:
        self._data = data
        self._json_deserializer = json_deserializer or json.loads

    @property
    def raw_event(self) -> dict[str, Any]:
        return self._data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)



class BaseProxyEvent(DictWrapper):
    
    @property
    def headers(self) -> dict[str, str]:
        return CaseInsensitiveDict(self.get("headers"))
    
    @property
    def query_string_parameters(self) -> dict[str, str]:
        return self.get("queryStringParameters", {}) or {}
    
    @property
    def multi_value_query_string_parameters(self) -> dict[str, list[str]]:
        return self.get("multiValueQueryStringParameters", {}) or {}
    
    @property
    def resolved_query_string_parameters(self) -> dict[str, list[str]]:
        return {k: v.split(",") for k, v in self.query_string_parameters.items()}

    @property
    def resolved_headers_field(self) -> dict[str, str]:
        return self.headers

    @property
    def is_base64_encoded(self) -> bool:
        return self.get("isBase64Encoded", False)
    
    @property
    def body(self) -> str | None:
        """ return body of the request as string"""
        return self.get("body")
    
    @cached_property
    def json_body(self) -> Any:
        """Parses the body as json"""
        if self.decoded_body:
            return self._json_deserializer(self.decoded_body)
        return None

    @cached_property
    def decoded_body(self) -> str | None:
        """ return body from base64 if encoded, otherwise return raw body"""
        body = self.body
        if self.is_base64_encoded and body:
            return base64.b64decode(body.encode()).decode()
        return body


    @property
    def path(self)->str:
        return self['path']
    
    @property
    def http_method(self)->str:
        return self['httpMethod']
    

    @overload
    def get_query_string_value(self, name: str, default_value: str) -> str: ...

    @overload
    def get_query_string_value(self, name: str, default_value: str | None = None) -> str | None: ...

    def get_query_string_value(self, name: str, default_value: str | None = None) -> str | None:
        """Get query string value by name"""
        return self.query_string_parameters.get(name, default_value)

    def get_multi_value_query_string_values(self, name: str, default_values: list[str] | None = None) -> list[str]:
        """Get multi value query string values by name"""
        default = default_values or []
        return self.multi_value_query_string_parameters.get(name, default)

    def header_serializer(self) -> BaseHeadersSerializer:
        raise NotImplementedError()


class RequestContextClientCert(DictWrapper):
    @property
    def client_cert_pem(self) -> str:
        """Client certificate pem"""
        return self["clientCertPem"]

    @property
    def issuer_dn(self) -> str:
        """Issuer Distinguished Name"""
        return self["issuerDN"]

    @property
    def serial_number(self) -> str:
        """Unique serial number for client cert"""
        return self["serialNumber"]

    @property
    def subject_dn(self) -> str:
        """Subject Distinguished Name"""
        return self["subjectDN"]

    @property
    def validity_not_after(self) -> str:
        """Date when the cert is no longer valid

        eg: Aug  5 00:28:21 2120 GMT"""
        return self["validity"]["notAfter"]

    @property
    def validity_not_before(self) -> str:
        """Cert is not valid before this date

        eg: Aug 29 00:28:21 2020 GMT"""
        return self["validity"]["notBefore"]


class APIGatewayEventIdentity(DictWrapper):
    @property
    def access_key(self) -> str | None:
        return self.get("accessKey")

    @property
    def account_id(self) -> str | None:
        """The AWS account ID associated with the request."""
        return self.get("accountId")

    @property
    def api_key(self) -> str | None:
        """For API methods that require an API key, this variable is the API key associated with the method request.
        For methods that don't require an API key, this variable is null."""
        return self.get("apiKey")

    @property
    def api_key_id(self) -> str | None:
        """The API key ID associated with an API request that requires an API key."""
        return self.get("apiKeyId")

    @property
    def caller(self) -> str | None:
        """The principal identifier of the caller making the request."""
        return self.get("caller")

    @property
    def cognito_authentication_provider(self) -> str | None:
        """A comma-separated list of the Amazon Cognito authentication providers used by the caller
        making the request. Available only if the request was signed with Amazon Cognito credentials."""
        return self.get("cognitoAuthenticationProvider")

    @property
    def cognito_authentication_type(self) -> str | None:
        """The Amazon Cognito authentication type of the caller making the request.
        Available only if the request was signed with Amazon Cognito credentials."""
        return self.get("cognitoAuthenticationType")

    @property
    def cognito_identity_id(self) -> str | None:
        """The Amazon Cognito identity ID of the caller making the request.
        Available only if the request was signed with Amazon Cognito credentials."""
        return self.get("cognitoIdentityId")

    @property
    def cognito_identity_pool_id(self) -> str | None:
        """The Amazon Cognito identity pool ID of the caller making the request.
        Available only if the request was signed with Amazon Cognito credentials."""
        return self.get("cognitoIdentityPoolId")

    @property
    def principal_org_id(self) -> str | None:
        """The AWS organization ID."""
        return self.get("principalOrgId")

    @property
    def source_ip(self) -> str:
        """The source IP address of the TCP connection making the request to API Gateway."""
        return self["sourceIp"]

    @property
    def user(self) -> str | None:
        """The principal identifier of the user making the request."""
        return self.get("user")

    @property
    def user_agent(self) -> str | None:
        """The User Agent of the API caller."""
        return self.get("userAgent")

    @property
    def user_arn(self) -> str | None:
        """The Amazon Resource Name (ARN) of the effective user identified after authentication."""
        return self.get("userArn")

    @property
    def client_cert(self) -> RequestContextClientCert | None:
        client_cert = self.get("clientCert")
        return None if client_cert is None else RequestContextClientCert(client_cert)



class BaseRequestContext(DictWrapper):
    @property
    def account_id(self) -> str:
        """The AWS account ID associated with the request."""
        return self["accountId"]

    @property
    def api_id(self) -> str:
        """The identifier API Gateway assigns to your API."""
        return self["apiId"]

    @property
    def domain_name(self) -> str | None:
        """A domain name"""
        return self.get("domainName")

    @property
    def domain_prefix(self) -> str | None:
        return self.get("domainPrefix")

    @property
    def extended_request_id(self) -> str | None:
        """An automatically generated ID for the API call, which contains more useful information
        for debugging/troubleshooting."""
        return self.get("extendedRequestId")

    @property
    def protocol(self) -> str:
        """The request protocol, for example, HTTP/1.1."""
        return self["protocol"]

    @property
    def http_method(self) -> str:
        """The HTTP method used. Valid values include: DELETE, GET, HEAD, OPTIONS, PATCH, POST, and PUT."""
        return self["httpMethod"]

    @property
    def identity(self) -> APIGatewayEventIdentity:
        return APIGatewayEventIdentity(self["identity"])

    @property
    def path(self) -> str:
        return self["path"]

    @property
    def stage(self) -> str:
        """The deployment stage of the API request"""
        return self["stage"]

    @property
    def request_id(self) -> str:
        """The ID that API Gateway assigns to the API request."""
        return self["requestId"]

    @property
    def request_time(self) -> str | None:
        """The CLF-formatted request time (dd/MMM/yyyy:HH:mm:ss +-hhmm)"""
        return self.get("requestTime")

    @property
    def request_time_epoch(self) -> int:
        """The Epoch-formatted request time."""
        return self["requestTimeEpoch"]

    @property
    def resource_id(self) -> str:
        return self["resourceId"]

    @property
    def resource_path(self) -> str:
        return self["resourcePath"]


class RequestContextV2Http(DictWrapper):
    @property
    def method(self) -> str:
        return self["method"]

    @property
    def path(self) -> str:
        return self["path"]

    @property
    def protocol(self) -> str:
        """The request protocol, for example, HTTP/1.1."""
        return self["protocol"]

    @property
    def source_ip(self) -> str:
        """The source IP address of the TCP connection making the request to API Gateway."""
        return self["sourceIp"]

    @property
    def user_agent(self) -> str:
        """The User Agent of the API caller."""
        return self["userAgent"]


class BaseRequestContextV2(DictWrapper):
    @property
    def account_id(self) -> str:
        """The AWS account ID associated with the request."""
        return self["accountId"]

    @property
    def api_id(self) -> str:
        """The identifier API Gateway assigns to your API."""
        return self["apiId"]

    @property
    def domain_name(self) -> str:
        """A domain name"""
        return self["domainName"]

    @property
    def domain_prefix(self) -> str:
        return self["domainPrefix"]

    @property
    def http(self) -> RequestContextV2Http:
        return RequestContextV2Http(self["http"])

    @property
    def request_id(self) -> str:
        """The ID that API Gateway assigns to the API request."""
        return self["requestId"]

    @property
    def route_key(self) -> str:
        """The selected route key."""
        return self["routeKey"]

    @property
    def stage(self) -> str:
        """The deployment stage of the API request"""
        return self["stage"]

    @property
    def time(self) -> str:
        """The CLF-formatted request time (dd/MMM/yyyy:HH:mm:ss +-hhmm)."""
        return self["time"]

    @property
    def time_epoch(self) -> int:
        """The Epoch-formatted request time."""
        return self["timeEpoch"]

    @property
    def authentication(self) -> RequestContextClientCert | None:
        """Optional when using mutual TLS authentication"""
        authentication = self.get("authentication") or {}
        client_cert = authentication.get("clientCert")
        return None if client_cert is None else RequestContextClientCert(client_cert)
