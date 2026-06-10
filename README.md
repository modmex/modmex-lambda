# modmex-lambda

Ultra-lightweight AWS Lambda utilities for API Gateway-first workloads.

`modmex-lambda` is a Lambda utility layer, not an ASGI framework. It focuses on
API Gateway proxy events, fast routing, request binding, response serialization,
middleware, dependency injection, event source wrappers, parsing, and structured
logging with a small dependency footprint.

## Install

```bash
pip install modmex-lambda
```


To use the optional `injector` integration:

```bash
pip install "modmex-lambda[injector]"
```

With Poetry:

```bash
poetry add "modmex-lambda[injector]"
```

## API Gateway Resolvers

Choose the resolver that matches the API Gateway payload version used by your
Lambda integration:

- `ApiGatewayRestResolver` for REST API payload v1.
- `ApiGatewayHttpResolver` for HTTP API payload v2 and Lambda Function URLs.

```python
from modmex_lambda import ApiGatewayHttpResolver

app = ApiGatewayHttpResolver()


@app.get("/ping")
def ping():
    return {"message": "pong"}


def handler(event, context):
    return app.resolve(event, context)

```

The internal base resolver is intentionally not exported from the package root;
application code should select REST or HTTP explicitly.

## Routing

Routes are declared with decorators:

```python
@app.get("/users/<user_id>")
def get_user(user_id: int):
    return {"user_id": user_id}


@app.post("/users", status_code=201)
def create_user():
    return {"id": 42}
```

Supported route decorators include `get`, `post`, `put`, `patch`, `delete`,
`options`, and `any`.

You can also declare routes on a standalone router and include it in the
resolver:

```python
from modmex_lambda import ApiGatewayHttpResolver
from modmex_lambda.routing import Router

app = ApiGatewayHttpResolver()
router = Router()


@router.get("/health")
def health():
    return {"ok": True}


app.include_router(router)
```

Routers can also strip deployment prefixes:

```python
app = ApiGatewayHttpResolver(strip_prefixes=["/prod"])
```

## Request Binding

Use `typing.Annotated` with the public parameter markers:

- `Path()`
- `Query()`
- `Header()`
- `Cookie()`
- `Body()`

```python
from typing import Annotated

from modmex import BaseModel
from modmex_lambda import ApiGatewayHttpResolver, Request
from modmex_lambda.event_handler.params import Body, Header, Path, Query

app = ApiGatewayHttpResolver()


class CreateUserRequest(BaseModel):
    name: str
    age: int | None = None


@app.post("/users", status_code=201)
def create_user(
    payload: Annotated[CreateUserRequest, Body()],
    tenant_id: Annotated[str, Header(name="x-tenant-id")],
    request: Request,
):
    return {
        "id": 42,
        "tenant_id": tenant_id,
        "route": request.route,
        "payload": payload.model_dump(),
    }


@app.get("/users/<user_id>")
def get_user(
    user_id: Annotated[int, Path()],
    include_orders: Annotated[bool, Query()] = False,
):
    return {"user_id": user_id, "include_orders": include_orders}
```

For headers, simple scalar parameters can use `Header(name="x-header-name")`.
Header models are also supported; field names are exposed as dash-case aliases.

```python
class HeaderModel(BaseModel):
    x_tenant_id: str


@app.get("/me")
def me(headers: Annotated[HeaderModel, Header()]):
    return {"tenant": headers.x_tenant_id}
```

## Responses

Route return values are converted to API Gateway proxy responses:

- `dict` and `list` become JSON responses.
- `str` becomes a text response.
- `bytes` are base64 encoded.
- `None` returns an empty response.
- `(body, status_code)` sets the response status.
- `Response` gives full control over status, headers, cookies, and content type.

Use plain return values for simple JSON endpoints:

```python
from modmex import BaseModel


class User(BaseModel):
    id: int
    name: str


@app.get("/users/<user_id>")
def get_user(user_id: int):
    user = User(id=user_id, name="Ada")
    return user.model_dump()


@app.post("/users", status_code=201)
def create_user():
    user = User(id=42, name="Ada")
    return user.model_dump()


@app.delete("/users/<user_id>")
def delete_user(user_id: int):
    return {"deleted": user_id}, 202
```

Use `Response` when the endpoint needs explicit response metadata. If you are
returning the same `User` model, pass `user.model_dump_json()` as the body and
set `content_type="application/json"`:

```python
from modmex_lambda import Response
from modmex_lambda.shared.cookies import Cookie


@app.get("/session")
def session():
    user = User(id=42, name="Ada")
    return Response(
        status_code=200,
        content_type="application/json",
        body=user.model_dump_json(),
        headers={"x-app": "users"},
        cookies=[
            Cookie(
                "session",
                "abc",
                path="/",
                http_only=True,
                secure=True,
                max_age=3600,
            ),
        ],
    )
```

`Response` accepts:

- `status_code`: the HTTP status code returned to API Gateway.
- `body`: a JSON-serializable object, `str`, `bytes`, or `None`.
- `content_type`: sets `Content-Type` unless the header is already present.
- `headers`: a mapping of header names to a string or list of strings.
- `cookies`: a list of `Cookie` objects.
- `compress`: overrides route-level gzip compression for that response.

When `Content-Type` starts with `application/json`, non-string bodies are
serialized with the app serializer. Binary bodies are base64 encoded.

For `modmex` models, prefer `model_dump()` when returning plain JSON objects.
Use `model_dump_json()` when you already need to build a `Response` and want to
send the serialized JSON string directly with `content_type="application/json"`.

```python
@app.get("/avatar/<user_id>")
def avatar(user_id: int):
    image_bytes = load_avatar(user_id)
    return Response(
        status_code=200,
        content_type="image/png",
        body=image_bytes,
        headers={"Cache-Control": "max-age=3600"},
    )
```

Route options can add response behavior without constructing `Response` in every
handler:

```python
@app.get("/report", cache_control="max-age=60", compress=True)
def report():
    return {"items": build_report()}
```

Compression is applied only when the request includes `Accept-Encoding: gzip`.
REST API responses use `multiValueHeaders`; HTTP API responses use the v2
`headers` and `cookies` shape.

## Middleware

Middleware receives the resolver instance and a `next_middleware` callable.
Global middleware can be registered with `use` or `@app.middleware`; route
middleware can be attached per route.

```python
from modmex_lambda import Response
from modmex_lambda.event_handler.middlewares import NextMiddleware


@app.middleware
def require_auth(app: ApiGatewayHttpResolver, next_middleware: NextMiddleware) -> Response:
    if app.current_event.headers.get("x-auth") != "ok":
        return Response(status_code=401, body={"message": "Unauthorized"})
    return next_middleware(app)
```

Middleware also wraps routing fallbacks, so `404` and `405` responses still flow
through the middleware chain.

## Dependency Injection

`Depends` supports nested dependency trees, request-aware dependencies,
per-invocation caching, and overrides for tests.

```python
from typing import Annotated

from modmex_lambda import Depends, Request
from modmex_lambda.event_handler.params import Path


class UserRepository:
    def __init__(self, *, tenant_id: str, token: str):
        self.tenant_id = tenant_id
        self.token = token

    def get_user(self, user_id: int) -> dict:
        # Replace this with a database or service call.
        return {"id": user_id, "tenant_id": self.tenant_id}


def get_token() -> str:
    return "token"


def get_tenant_id(request: Request) -> str:
    return request.headers["x-tenant-id"]


def get_user_repository(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    token: Annotated[str, Depends(get_token)],
) -> UserRepository:
    return UserRepository(tenant_id=tenant_id, token=token)


@app.get("/users/<user_id>")
def get_user(
    user_id: Annotated[int, Path()],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
):
    return repository.get_user(user_id)
```

For constructor-heavy services, install the optional `injector` extra and pass
an `InjectorDependencyResolver` to the app. `Depends()` without a callable uses
the parameter annotation as the dependency token.

```python
from typing import Annotated

from injector import Injector, Module, inject, provider, singleton
from modmex_lambda import ApiGatewayHttpResolver, Depends, InjectorDependencyResolver
from modmex_lambda.event_handler.params import Path


class Settings:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id


class UserRepository:
    def __init__(self, settings: Settings):
        self.settings = settings

    def get_user(self, user_id: int) -> dict:
        return {"id": user_id, "tenant_id": self.settings.tenant_id}


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def get_user(self, user_id: int) -> dict:
        return self.repository.get_user(user_id)


class AppModule(Module):
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


container = Injector([AppModule()])
app = ApiGatewayHttpResolver(dependency_resolver=InjectorDependencyResolver(container))

@app.get("/users/<user_id>")
def get_user(
    user_id: Annotated[int, Path()],
    service: Annotated[UserService, Depends()],
):
    return service.get_user(user_id)
```

Disable dependency caching when a dependency must run every time:

```python
def next_counter() -> int:
    ...


@app.get("/counter")
def counter(value: Annotated[int, Depends(next_counter, use_cache=False)]):
    return {"value": value}
```

For tests, set `app.dependency_overrides`:

```python
app.dependency_overrides[get_token] = lambda: "test-token"
```

## Exception Handling

Built-in error responses:

- request validation errors return `400`.
- `NotFoundError` returns `404`.
- `MethodNotAllowedError` returns `405`.
- `UnauthorizedError` returns `401`.
- `ForbiddenError` returns `403`.

Custom handlers can be registered per exception type. The most specific handler
wins.

```python
from modmex_lambda import Response


class DomainError(Exception):
    pass


@app.exception_handler(DomainError)
def on_domain_error(exc: DomainError):
    return Response(status_code=409, body={"message": str(exc)})
```

If a custom exception handler raises, the resolver falls back to the default
error response when one exists.

## CORS

Pass `CORSConfig` to the resolver to add CORS headers and automatic preflight
behavior.

```python
from modmex_lambda import ApiGatewayHttpResolver
from modmex_lambda.event_handler.cors import CORSConfig

app = ApiGatewayHttpResolver(
    cors=CORSConfig(
        allow_origin="https://app.example",
        allow_headers=["X-Tenant-Id"],
        allow_credentials=True,
    ),
)
```

## Parser

```python
from modmex_lambda.parser import event_parser, parse

parsed = parse(event={"name": "Ada"}, model=MyModel)


@event_parser(model=MyModel)
def lambda_handler(event: MyModel, context):
    ...
```

## Event Source Data Classes

Current scoped data classes include:

- `APIGatewayProxyEvent` and `APIGatewayProxyEventV2`
- `APIGatewayRestEvent` and `APIGatewayHttpEvent` aliases
- `APIGatewayAuthorizerEvent`
- `APIGatewayWebSocketEvent`
- Cognito User Pool trigger wrappers

```python
from modmex_lambda.data_classes import APIGatewayHttpEvent
from modmex_lambda.event_sources import event_source


@event_source(data_class=APIGatewayHttpEvent)
def lambda_handler(event: APIGatewayHttpEvent, context):
    return {"path": event.path}
```

## Validation

Modmex is the default validation and coercion engine. It is used for path,
query, header, cookie, and body parameters declared with `Annotated`, and it is
paired with the default JSON serializer for common values like enums, dates,
datetimes, decimals, and dataclasses.

```python
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from modmex import BaseModel
from modmex_lambda import ApiGatewayHttpResolver
from modmex_lambda.event_handler.params import Body, Path, Query

app = ApiGatewayHttpResolver()


class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"


class CreateAccount(BaseModel):
    name: str
    plan: Plan = Plan.FREE
    trial_ends_on: date | None = None


class Account(BaseModel):
    id: int
    name: str
    plan: Plan
    balance: Decimal


@app.post("/accounts", status_code=201)
def create_account(payload: Annotated[CreateAccount, Body()]):
    account = Account(
        id=42,
        name=payload.name,
        plan=payload.plan,
        balance=Decimal("0.00"),
    )
    # Return model_dump() when you want the response body to be a JSON object.
    return account.model_dump()


@app.get("/accounts/<account_id>")
def get_account(
    account_id: Annotated[int, Path()],
    include_usage: Annotated[bool, Query()] = False,
):
    return {
        "id": account_id,
        "include_usage": include_usage,
        "created_on": date(2026, 1, 1),
    }
```

If validation fails, the resolver returns `400` with a compact validation error
payload. For domain-specific errors, register an exception handler and return a
`Response` with the shape your API expects.

## Logging

```python
from modmex_lambda import Logger

logger = Logger(service="users")


def lambda_handler(event, context):
    logger.append_keys(tenant_id="mx")
    logger.info("request received")
```

The logger emits structured JSON and can extract Lambda request IDs and API
Gateway correlation IDs.


## Limitations

- Event source scope is intentionally focused on API Gateway and Cognito.
- OpenAPI/Swagger generation is not implemented.
- Async resolver pipelines are not implemented yet.
