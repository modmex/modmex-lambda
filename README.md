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

For local development:

```bash
poetry install --extras dev
poetry run pytest -q
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


handler = app.handler
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

```python
from modmex_lambda import Response
from modmex_lambda.shared.cookies import Cookie


@app.get("/session")
def session():
    return Response(
        status_code=200,
        body={"ok": True},
        cookies=[Cookie("seen", "true", secure=True)],
    )
```

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

Modmex is the default validation and coercion engine. Pydantic is not required
for normal operation.

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

## Benchmarks

The benchmark suite lives in `.benchmark/api_gateway_benchmark.py`.

It covers cold imports, app setup, route registration, API Gateway v1/v2
invocation, `event_parser`, `event_source`, and logger hot paths.

```bash
poetry run python .benchmark/api_gateway_benchmark.py
```

More details are in `.benchmark/README.md`.

## Limitations

- Event source scope is intentionally focused on API Gateway and Cognito.
- OpenAPI/Swagger generation is not implemented.
- Async resolver pipelines are not implemented yet.
