from __future__ import annotations

import base64
import gzip
import json
import re
from collections import defaultdict
from enum import Enum
from typing import Annotated

import pytest

import modmex_lambda
from modmex_lambda import APIGatewayHttpResolver, APIGatewayRestResolver, Depends
from modmex_lambda.event_handler import content_types
from modmex_lambda.event_handler.api_gateway import ApiGatewayResolver, Request, Response
from modmex_lambda.event_handler.cors import CORSConfig
from modmex_lambda.event_handler.exceptions import ForbiddenError, MethodNotAllowedError, NotFoundError, UnauthorizedError
from modmex_lambda.event_handler.middlewares import NextMiddleware
from modmex_lambda.event_handler.params import Body, Header, Path, Query
from modmex_lambda.event_handler.routing import Router
from modmex_lambda.shared.cookies import Cookie
from tests.conftest import http_v2_event, response_body, rest_event


class CreateUserRequest:
    def __init__(self, name: str, age: int | None = None) -> None:
        self.name = name
        self.age = age


class Settings:
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id


class UserRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_user(self, user_id: int) -> dict[str, str | int]:
        return {"id": user_id, "tenant_id": self.settings.tenant_id}


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def get_user(self, user_id: int) -> dict[str, str | int]:
        return self.repository.get_user(user_id)


class AuditService:
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    def record(self, user_id: int) -> dict[str, str | int]:
        return {"user_id": user_id, "tenant_id": self.tenant_id}


def test_public_api_requires_explicit_api_gateway_resolver() -> None:
    assert modmex_lambda.APIGatewayHttpResolver is APIGatewayHttpResolver
    assert modmex_lambda.APIGatewayRestResolver is APIGatewayRestResolver
    assert "ApiGatewayResolver" not in dir(modmex_lambda)
    assert content_types.APPLICATION_JSON == "application/json"


def test_base_resolver_direct_use_fails_with_actionable_error() -> None:
    app = ApiGatewayResolver()

    with pytest.raises(TypeError, match="Use APIGatewayRestResolver"):
        app.resolve(http_v2_event("GET", "/ping"), object())


def test_resolver_rejects_unknown_event_type() -> None:
    class UnknownEventType(Enum):
        UNKNOWN = "unknown"

    class UnknownResolver(ApiGatewayResolver):
        _event_type = UnknownEventType.UNKNOWN

    with pytest.raises(TypeError, match="Unsupported API Gateway event type"):
        UnknownResolver().resolve(http_v2_event("GET", "/ping"), object())


def test_http_resolver_binds_path_query_header_and_request_facade() -> None:
    app = APIGatewayHttpResolver()

    @app.get("/users/<user_id>")
    def get_user(
        user_id: Annotated[int, Path()],
        tenant_id: Annotated[str, Header(name="x-tenant-id")],
        include_orders: Annotated[bool, Query()] = False,
        request: Request | None = None,
    ):
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "include_orders": include_orders,
            "request": {
                "method": request.method,
                "route": request.route,
                "query": request.query_parameters,
            },
        }

    response = app.resolve(
        http_v2_event(
            "GET",
            "/users/42",
            headers={"X-Tenant-Id": "mx"},
            query={"include_orders": "true"},
        ),
        object(),
    )

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/json"
    assert response["cookies"] == []
    assert response_body(response) == {
        "user_id": 42,
        "tenant_id": "mx",
        "include_orders": True,
        "request": {
            "method": "GET",
            "route": "/users/<user_id>",
            "query": {"include_orders": "true"},
        },
    }


def test_request_facade_requires_route_and_is_cached_inside_middleware() -> None:
    app = APIGatewayHttpResolver()
    seen: list[bool] = []

    with pytest.raises(RuntimeError):
        app.request

    @app.middleware
    def capture_request(resolver: ApiGatewayResolver, next_middleware: NextMiddleware) -> Response:
        seen.append(resolver.request is resolver.request)
        return next_middleware(resolver)

    @app.get("/request")
    def request_handler():
        return {"ok": True}

    response = app.resolve(http_v2_event("GET", "/request"), object())

    assert response_body(response) == {"ok": True}
    assert seen == [True]


def test_injected_request_path_parameters_only_include_path_values() -> None:
    app = APIGatewayHttpResolver()

    @app.put("/users/<user_id>")
    def update_user(
        user_id: Annotated[int, Path()],
        payload: Annotated[CreateUserRequest, Body()],
        request: Request | None = None,
    ):
        return {"path_parameters": request.path_parameters}

    response = app.resolve(http_v2_event("PUT", "/users/42", body={"name": "Ada"}), object())

    assert response_body(response) == {"path_parameters": {"user_id": "42"}}


def test_rest_resolver_uses_rest_proxy_response_shape() -> None:
    app = APIGatewayRestResolver()

    @app.get("/ping")
    def ping():
        return Response(
            status_code=200,
            content_type=content_types.APPLICATION_JSON,
            body={"ok": True},
            headers={"x-app": "modmex"},
            cookies=[Cookie("seen", "true")],
        )

    response = app.resolve(rest_event("GET", "/ping"), object())

    assert response["statusCode"] == 200
    assert "headers" not in response
    assert response["multiValueHeaders"]["Content-Type"] == ["application/json"]
    assert response["multiValueHeaders"]["x-app"] == ["modmex"]
    assert response["multiValueHeaders"]["Set-Cookie"] == ["seen=true; Secure"]
    assert response_body(response) == {"ok": True}


def test_http_resolver_serializes_cookies_in_http_api_shape() -> None:
    app = APIGatewayHttpResolver()

    @app.get("/session")
    def session():
        return Response(
            status_code=200,
            content_type=content_types.APPLICATION_JSON,
            body={"ok": True},
            cookies=[Cookie("seen", "true")],
        )

    response = app.resolve(http_v2_event("GET", "/session"), object())

    assert response["headers"]["Content-Type"] == "application/json"
    assert response["cookies"] == ["seen=true; Secure"]
    assert response_body(response) == {"ok": True}


def test_static_dynamic_any_404_and_405_routing() -> None:
    app = APIGatewayHttpResolver()

    @app.get("/users/<user_id>")
    def get_user(user_id: Annotated[int, Path()]):
        return {"user_id": user_id}

    @app.route("/proxy", method="ANY")
    def proxy():
        return {"proxied": True}

    ok = app.resolve(http_v2_event("GET", "/users/7"), None)
    any_route = app.resolve(http_v2_event("PATCH", "/proxy"), None)
    not_allowed = app.resolve(http_v2_event("POST", "/users/7"), None)
    not_found = app.resolve(http_v2_event("GET", "/missing"), None)

    assert response_body(ok) == {"user_id": 7}
    assert response_body(any_route) == {"proxied": True}
    assert not_allowed["statusCode"] == 405
    assert not_allowed["headers"]["Allow"] == "GET"
    assert response_body(not_allowed) == {"statusCode": 405, "message": "Method Not Allowed"}
    assert not_found["statusCode"] == 404
    assert response_body(not_found) == {"statusCode": 404, "message": "Not Found"}


def test_rest_resolver_serializes_not_found_with_rest_proxy_shape() -> None:
    app = APIGatewayRestResolver()

    response = app.resolve(rest_event("GET", "/missing"), object())

    assert response["statusCode"] == 404
    assert "headers" not in response
    assert response["multiValueHeaders"]["Content-Type"] == ["application/json"]
    assert response_body(response) == {"statusCode": 404, "message": "Not Found"}


def test_custom_routing_fallback_exception_handlers() -> None:
    app = APIGatewayHttpResolver()

    @app.get("/users")
    def users():
        return {"ok": True}

    @app.exception_handler(NotFoundError)
    def on_not_found(_exc: Exception):
        return Response(
            status_code=499,
            content_type=content_types.APPLICATION_JSON,
            body={"handler": "not-found"},
        )

    @app.exception_handler(MethodNotAllowedError)
    def on_method_not_allowed(_exc: Exception):
        return Response(
            status_code=498,
            content_type=content_types.APPLICATION_JSON,
            body={"handler": "method-not-allowed"},
        )

    not_found = app.resolve(http_v2_event("GET", "/missing"), object())
    method_not_allowed = app.resolve(http_v2_event("POST", "/users"), object())

    assert not_found["statusCode"] == 499
    assert response_body(not_found) == {"handler": "not-found"}
    assert method_not_allowed["statusCode"] == 498
    assert response_body(method_not_allowed) == {"handler": "method-not-allowed"}


def test_include_router_and_strip_prefixes() -> None:
    router = Router()
    app = APIGatewayHttpResolver(strip_prefixes=["/prod"])

    @router.get("/health")
    def health():
        return {"ok": True}

    app.include_router(router)

    response = app.resolve(http_v2_event("GET", "/prod/health"), object())

    assert response_body(response) == {"ok": True}


def test_include_nested_routers() -> None:
    grandchild = Router()
    child = Router()
    parent = Router()
    app = APIGatewayHttpResolver()

    @grandchild.get("/health")
    def health():
        return {"ok": True}

    child.include_router(grandchild, prefix="/v1")
    parent.include_router(child, prefix="/api")
    app.include_router(parent)

    response = app.resolve(http_v2_event("GET", "/api/v1/health"), object())

    assert response_body(response) == {"ok": True}


def test_strip_prefix_exact_match_and_regex_prefix() -> None:
    app = APIGatewayHttpResolver(strip_prefixes=["/prod"])
    regex_app = APIGatewayHttpResolver(strip_prefixes=[re.compile(r"^/v[0-9]+")])

    @app.get("/")
    def root():
        return {"root": True}

    @regex_app.get("/health")
    def health():
        return {"ok": True}

    assert response_body(app.resolve(http_v2_event("GET", "/prod"), object())) == {"root": True}
    assert response_body(regex_app.resolve(http_v2_event("GET", "/v2/health"), object())) == {"ok": True}


def test_global_and_route_middlewares_wrap_success_404_and_405() -> None:
    app = APIGatewayHttpResolver()
    calls: list[str] = []

    def global_header(resolver: ApiGatewayResolver, next_middleware: NextMiddleware) -> Response:
        calls.append(f"global:{resolver.current_event.path}")
        response = next_middleware(resolver)
        response.headers["x-global"] = "yes"
        return response

    def route_header(resolver: ApiGatewayResolver, next_middleware: NextMiddleware) -> Response:
        calls.append("route")
        response = next_middleware(resolver)
        response.headers["x-route"] = "yes"
        return response

    app.use([global_header])

    @app.get("/ok", middlewares=[route_header])
    def ok():
        return {"ok": True}

    success = app.resolve(http_v2_event("GET", "/ok"), object())
    missing = app.resolve(http_v2_event("GET", "/missing"), object())
    method_not_allowed = app.resolve(http_v2_event("POST", "/ok"), object())

    assert response_body(success) == {"ok": True}
    assert success["headers"]["x-global"] == "yes"
    assert success["headers"]["x-route"] == "yes"
    assert missing["statusCode"] == 404
    assert missing["headers"]["x-global"] == "yes"
    assert "x-route" not in missing["headers"]
    assert method_not_allowed["statusCode"] == 405
    assert method_not_allowed["headers"]["x-global"] == "yes"
    assert "x-route" not in method_not_allowed["headers"]
    assert calls == ["global:/ok", "route", "global:/missing", "global:/ok"]


def test_middleware_decorator_order_and_short_circuit() -> None:
    app = APIGatewayHttpResolver()
    order: list[str] = []

    @app.middleware
    def first(resolver: ApiGatewayResolver, next_middleware: NextMiddleware) -> Response:
        order.append("first_before")
        response = next_middleware(resolver)
        order.append("first_after")
        return response

    @app.middleware
    def auth(resolver: ApiGatewayResolver, next_middleware: NextMiddleware) -> Response:
        order.append("auth")
        if resolver.current_event.headers.get("x-auth") != "ok":
            return Response(
                status_code=401,
                content_type=content_types.APPLICATION_JSON,
                body={"message": "Unauthorized"},
            )
        return next_middleware(resolver)

    @app.get("/secure")
    def secure():
        order.append("handler")
        return {"message": "allowed"}

    denied = app.resolve(http_v2_event("GET", "/secure"), object())
    allowed = app.resolve(http_v2_event("GET", "/secure", headers={"x-auth": "ok"}), object())

    assert denied["statusCode"] == 401
    assert response_body(denied) == {"message": "Unauthorized"}
    assert response_body(allowed) == {"message": "allowed"}
    assert order == ["first_before", "auth", "first_after", "first_before", "auth", "handler", "first_after"]


def test_dependency_injection_cache_overrides_and_request_dependency() -> None:
    app = APIGatewayHttpResolver()
    counters = defaultdict(int)

    class UserRepository:
        def __init__(self, *, tenant_id: str, token: str) -> None:
            self.tenant_id = tenant_id
            self.token = token

        def get_user(self, user_id: int) -> dict[str, str | int]:
            return {"id": user_id, "tenant_id": self.tenant_id, "token": self.token}

    class AccessAudit:
        def __init__(self, token: str) -> None:
            self.token = token

        def record_user_read(self, user_id: int) -> dict[str, str | int]:
            return {"user_id": user_id, "token": self.token}

    def get_token() -> str:
        counters["token"] += 1
        return "t-1"

    def get_tenant_id(request: Request) -> str:
        return request.headers.get("x-tenant-id", "")

    def get_user_repository(
        token: Annotated[str, Depends(get_token)],
        tenant_id: Annotated[str, Depends(get_tenant_id)],
    ) -> UserRepository:
        counters["repo"] += 1
        return UserRepository(tenant_id=tenant_id, token=token)

    def get_access_audit(token: Annotated[str, Depends(get_token)]) -> AccessAudit:
        counters["audit"] += 1
        return AccessAudit(token)

    @app.get("/users/<user_id>")
    def handler(
        user_id: Annotated[int, Path()],
        repository: Annotated[UserRepository, Depends(get_user_repository)],
        audit: Annotated[AccessAudit, Depends(get_access_audit)],
    ):
        return {
            "user": repository.get_user(user_id),
            "audit": audit.record_user_read(user_id),
        }

    response = app.resolve(http_v2_event("GET", "/users/42", headers={"x-tenant-id": "mx"}), object())
    assert response_body(response) == {
        "user": {"id": 42, "tenant_id": "mx", "token": "t-1"},
        "audit": {"user_id": 42, "token": "t-1"},
    }
    assert counters == {"token": 1, "repo": 1, "audit": 1}

    app.dependency_overrides[get_token] = lambda: "override"
    overridden = app.resolve(http_v2_event("GET", "/users/42", headers={"x-tenant-id": "mx"}), object())

    assert response_body(overridden) == {
        "user": {"id": 42, "tenant_id": "mx", "token": "override"},
        "audit": {"user_id": 42, "token": "override"},
    }


def test_dependency_injection_without_cache() -> None:
    app = APIGatewayHttpResolver()
    calls = {"value": 0}

    def counter_factory() -> int:
        calls["value"] += 1
        return calls["value"]

    @app.get("/di-nocache")
    def handler(
        a: Annotated[int, Depends(counter_factory, use_cache=False)],
        b: Annotated[int, Depends(counter_factory, use_cache=False)],
    ):
        return {"a": a, "b": b}

    response = app.resolve(http_v2_event("GET", "/di-nocache"), object())

    assert response_body(response) == {"a": 1, "b": 2}


def test_dependency_injection_uses_custom_dependency_resolver_for_annotation_token() -> None:
    class UserService:
        def __init__(self, tenant_id: str) -> None:
            self.tenant_id = tenant_id

    class Resolver:
        def resolve(self, dependency, *, values=None):
            assert dependency is UserService
            assert values == {}
            return UserService(tenant_id="mx")

    app = APIGatewayHttpResolver(dependency_resolver=Resolver())

    @app.get("/di-resolver")
    def handler(service: Annotated[UserService, Depends()]):
        return {"tenant_id": service.tenant_id}

    response = app.resolve(http_v2_event("GET", "/di-resolver", headers={"x-tenant-id": "mx"}), object())

    assert response_body(response) == {"tenant_id": "mx"}


def test_http_resolver_supports_real_injector_class_token_dependency() -> None:
    pytest.importorskip("injector")
    from injector import Injector, Module, inject, provider, singleton
    from modmex_lambda import InjectorDependencyResolver

    class MyModule(Module):
        @singleton
        @provider
        def provide_settings(self) -> Settings:
            return Settings(tenant_id="mx")

        @singleton
        @provider
        @inject
        def provide_repository(self, settings: Settings) -> UserRepository:
            return UserRepository(settings)

        @singleton
        @provider
        @inject
        def provide_service(self, repository: UserRepository) -> UserService:
            return UserService(repository)

    container = Injector([MyModule()])
    app = APIGatewayHttpResolver(dependency_resolver=InjectorDependencyResolver(container))

    @app.get("/injector/users/<user_id>")
    def handler(
        user_id: Annotated[int, Path()],
        service: Annotated[UserService, Depends()],
    ):
        return service.get_user(user_id)

    response = app.resolve(http_v2_event("GET", "/injector/users/42"), object())

    assert response_body(response) == {"id": 42, "tenant_id": "mx"}


def test_rest_resolver_supports_real_injector_factory_dependency() -> None:
    pytest.importorskip("injector")
    from injector import Injector, Module, inject, provider, singleton
    from modmex_lambda import InjectorDependencyResolver

    class MyModule(Module):
        @singleton
        @provider
        def provide_settings(self) -> Settings:
            return Settings(tenant_id="mx")

    @inject
    def get_audit_service(settings: Settings) -> AuditService:
        return AuditService(settings.tenant_id)

    container = Injector([MyModule()])
    app = APIGatewayRestResolver(dependency_resolver=InjectorDependencyResolver(container))

    @app.get("/injector/audit/<user_id>")
    def handler(
        user_id: Annotated[int, Path()],
        audit: Annotated[AuditService, Depends(get_audit_service)],
    ):
        return audit.record(user_id)

    response = app.resolve(rest_event("GET", "/injector/audit/7"), object())

    assert response_body(response) == {"user_id": 7, "tenant_id": "mx"}


def test_validation_error_maps_to_400() -> None:
    app = APIGatewayHttpResolver()

    @app.get("/users/<user_id>")
    def get_user(user_id: Annotated[int, Path()]):
        return {"user_id": user_id}

    response = app.resolve(http_v2_event("GET", "/users/not-an-int"), object())

    assert response["statusCode"] == 400
    body = response_body(response)
    assert body["message"] == "Validation Error"
    assert body["detail"][0]["type"]


def test_custom_and_builtin_exception_handlers() -> None:
    app = APIGatewayHttpResolver()

    class DomainError(Exception):
        pass

    @app.exception_handler(DomainError)
    def on_domain_error(exc: Exception):
        return Response(status_code=409, content_type=content_types.APPLICATION_JSON, body={"message": str(exc)})

    @app.get("/conflict")
    def conflict():
        raise DomainError("already exists")

    @app.get("/auth")
    def auth():
        raise UnauthorizedError("missing token")

    @app.get("/forbidden")
    def forbidden():
        raise ForbiddenError("not allowed")

    assert app.resolve(http_v2_event("GET", "/conflict"), object())["statusCode"] == 409
    assert app.resolve(http_v2_event("GET", "/auth"), object())["statusCode"] == 401
    assert app.resolve(http_v2_event("GET", "/forbidden"), object())["statusCode"] == 403


def test_default_error_responses_for_explicit_route_errors() -> None:
    app = APIGatewayHttpResolver()

    @app.get("/not-found")
    def not_found():
        raise NotFoundError()

    @app.get("/method")
    def method():
        raise MethodNotAllowedError()

    assert app.resolve(http_v2_event("GET", "/not-found"), object())["statusCode"] == 404
    assert app.resolve(http_v2_event("GET", "/method"), object())["statusCode"] == 405


def test_exception_handler_failure_falls_back_to_default_error_response() -> None:
    app = APIGatewayHttpResolver()

    @app.exception_handler(ValueError)
    def broken_handler(_exc: Exception):
        raise UnauthorizedError()

    @app.get("/broken-handler")
    def broken_handler_route():
        raise ValueError("boom")

    response = app.resolve(http_v2_event("GET", "/broken-handler"), object())

    assert response["statusCode"] == 401


def test_most_specific_exception_handler_wins() -> None:
    app = APIGatewayHttpResolver()

    @app.exception_handler(Exception)
    def on_any(_exc: Exception):
        return Response(status_code=500, content_type=content_types.APPLICATION_JSON, body={"handler": "exception"})

    @app.exception_handler(ValueError)
    def on_value_error(_exc: Exception):
        return Response(status_code=400, content_type=content_types.APPLICATION_JSON, body={"handler": "value"})

    @app.get("/value")
    def value():
        raise ValueError("boom")

    response = app.resolve(http_v2_event("GET", "/value"), object())

    assert response["statusCode"] == 400
    assert response_body(response) == {"handler": "value"}


def test_cors_preflight_and_route_headers() -> None:
    app = APIGatewayHttpResolver(cors=CORSConfig(allow_origin="https://app.example"))

    @app.get("/users")
    def users():
        return {"ok": True}

    response = app.resolve(
        http_v2_event("GET", "/users", headers={"origin": "https://app.example"}),
        object(),
    )
    preflight = app.resolve(
        http_v2_event("OPTIONS", "/users", headers={"origin": "https://app.example"}),
        object(),
    )

    assert response["headers"]["Access-Control-Allow-Origin"] == "https://app.example"
    assert preflight["statusCode"] == 204
    assert preflight["headers"]["Access-Control-Allow-Methods"] == "GET,OPTIONS"


def test_cors_preflight_for_missing_route_uses_registered_cors_methods() -> None:
    app = APIGatewayHttpResolver(cors=CORSConfig(allow_origin="https://app.example"))

    @app.get("/users")
    def users():
        return {"ok": True}

    response = app.resolve(http_v2_event("OPTIONS", "/missing"), object())

    assert response["statusCode"] == 204
    assert response["headers"]["Access-Control-Allow-Methods"] == "GET"


def test_cache_control_and_gzip_compression() -> None:
    app = APIGatewayHttpResolver()

    @app.get("/compressed", cache_control="max-age=60", compress=True)
    def compressed():
        return {"message": "hello"}

    response = app.resolve(
        http_v2_event("GET", "/compressed", headers={"accept-encoding": "gzip"}),
        object(),
    )

    assert response["headers"]["Cache-Control"] == "max-age=60"
    assert response["headers"]["Content-Encoding"] == "gzip"
    assert response["isBase64Encoded"] is True
    assert json.loads(gzip.decompress(base64.b64decode(response["body"]))) == {"message": "hello"}
