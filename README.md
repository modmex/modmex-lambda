# modmex-lambda

AWS Lambda utilities for API Gateway and event-driven workloads.

[![CI](https://img.shields.io/github/actions/workflow/status/modmex/modmex/ci.yml?branch=main&logo=github&label=CI)](https://github.com/modmex/modmex/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/codecov/c/github/modmex/modmex-lambda?label=coverage)](https://codecov.io/gh/modmex/modmex-lambda)
[![PyPI](https://img.shields.io/pypi/v/modmex-lambda.svg)](https://pypi.org/project/modmex-lambda/)
[![Python Versions](https://img.shields.io/pypi/pyversions/modmex-lambda.svg)](https://pypi.org/project/modmex-lambda/)
[![License](https://img.shields.io/github/license/modmex/modmex-lambda.svg)](https://github.com/modmex/modmex-lambda/blob/main/LICENSE)

`modmex-lambda` is a Lambda utility layer, not an ASGI framework. It focuses on
API Gateway proxy events, fast routing, request binding, response serialization,
middleware, dependency injection, stream sources, parsing, and structured
logging.

The fuller documentation site lives in [`docs/`](docs/).

## Install

```bash
pip install modmex-lambda
```


`injector` support is included for REST and stream dependency resolution:

```bash
pip install modmex-lambda
```

With Poetry:

```bash
poetry add modmex-lambda
```

## API Gateway Resolvers

Choose the resolver that matches the API Gateway payload version used by your
Lambda integration:

- `APIGatewayRestResolver` for REST API payload v1.
- `APIGatewayHttpResolver` for HTTP API payload v2 and Lambda Function URLs.

```python
from modmex_lambda import APIGatewayHttpResolver

app = APIGatewayHttpResolver()


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
from modmex_lambda import APIGatewayHttpResolver
from modmex_lambda.routing import Router

app = APIGatewayHttpResolver()
router = Router()


@router.get("/health")
def health():
    return {"ok": True}


app.include_router(router)
```

Routers can also strip deployment prefixes:

```python
app = APIGatewayHttpResolver(strip_prefixes=["/prod"])
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
from modmex_lambda import APIGatewayHttpResolver, Request
from modmex_lambda.event_handler.params import Body, Header, Path, Query

app = APIGatewayHttpResolver()


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
def require_auth(app: APIGatewayHttpResolver, next_middleware: NextMiddleware) -> Response:
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

For constructor-heavy services, pass an `InjectorDependencyResolver` to the app.
`Depends()` without a callable uses the parameter annotation as the dependency
token.

```python
from typing import Annotated

from injector import Injector, Module, inject, provider, singleton
from modmex_lambda import APIGatewayHttpResolver, Depends, InjectorDependencyResolver
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
dependency_resolver = InjectorDependencyResolver(container)
app = APIGatewayHttpResolver(dependency_resolver=dependency_resolver)

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
from modmex_lambda import APIGatewayHttpResolver
from modmex_lambda.event_handler.cors import CORSConfig

app = APIGatewayHttpResolver(
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
from modmex_lambda import APIGatewayHttpResolver
from modmex_lambda.event_handler.params import Body, Path, Query

app = APIGatewayHttpResolver()


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

logger = Logger()


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    logger.append_keys(tenant_id="mx")
    logger.info("request received")
```

The logger emits structured JSON, reads `LOG_LEVEL`, uses `SERVICE_NAME` or
`AWS_LAMBDA_FUNCTION_NAME` when no service is passed, and can extract Lambda
request IDs and API Gateway correlation IDs. The `inject_lambda_context`
decorator resets logger state by default for warm Lambda invocations, injects
Lambda metadata, and can optionally log the incoming event.

## Tracing

Tracing is optional and lazy. The core package does not require
`opentelemetry-api`, does not initialize an SDK/exporter, and does not import
OpenTelemetry during `import modmex_lambda`.

`Tracer` uses OpenTelemetry when an OpenTelemetry runtime is available. For
Lambda, the recommended runtime is the AWS Distro for OpenTelemetry (ADOT)
Lambda layer.

The example below uses Serverless Framework. If you use another IaC tool, the
same pieces are required: enable Lambda tracing, attach the ADOT Python layer
for the AWS region where the function runs, and configure the OpenTelemetry
environment variables.

```yaml
provider:
  name: aws
  runtime: python3.12
  region: mx-central-1
  tracing:
    lambda: true

functions:
  api:
    handler: app.lambda_handler
    layers:
      - arn:aws:lambda:mx-central-1:610118373846:layer:AWSOpenTelemetryDistroPython:13
    environment:
      AWS_LAMBDA_EXEC_WRAPPER: /opt/otel-instrument
      OTEL_SERVICE_NAME: ${self:service}
```

Do not bundle `opentelemetry-*` packages in your function when using the ADOT
layer. The layer provides the OpenTelemetry runtime; bundling a different
version can conflict with the layer. Public ADOT layer ARNs are regional, so
use the ARN that matches your configured AWS region.

```python
from modmex_lambda import Tracer

tracer = Tracer(service="orders")


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    return handle(event)


@tracer.capture_method(name="handle_order")
def handle(event):
    tracer.set_attribute("tenant_id", event.get("tenant_id"))
    return {"ok": True}
```

If OpenTelemetry is not installed or configured, the tracer is a no-op. Use an
external OpenTelemetry setup, such as an ADOT Lambda layer or your own SDK
configuration, when spans should be exported.

When decorating route handlers, put the route decorator above
`capture_method`, so the router registers the traced function:

```python
@app.post("/todos")
@tracer.capture_method(name="create_todo")
def create_todo(todo: Annotated[Todo, Body()]) -> dict:
    return todo.model_dump()
```


## Stream Handlers

Event-driven Lambda handlers live under `modmex_lambda.stream`. Use them for
listeners and triggers backed by SQS, SNS, Kinesis, DynamoDB Streams, S3, and
other common AWS event sources.

```python
from modmex_lambda.stream.flavors.cdc import CdcRule, ChangeDataCapture
from modmex_lambda.stream.rules_registry import RulesRegistry
from modmex_lambda.stream.sources import dynamodb_source
from modmex_lambda.stream.utils.contracts import DynamoDBEvent, Uow


def to_user_created_event(uow: Uow[DynamoDBEvent]) -> DynamoDBEvent:
    user = uow["event"]["raw"]["new"]
    return {
        "id": f"user-created:{user['id']}",
        "type": "user-created",
        "partition_key": user["id"],
        "user": user,
    }


rule: CdcRule[DynamoDBEvent] = {
    "id": "publish-user-created",
    "event_type": "USER-created",
    "to_event": to_user_created_event,
}


registry = RulesRegistry().registry(
    ChangeDataCapture[DynamoDBEvent](rule)
)


@dynamodb_source(registry)
def handler(event, context):
    return {"statusCode": 200}
```

Streams include source normalizers, rule registries, filters, flavors, AWS
connectors, and operators for common event-driven patterns.

## Stream Core Concepts

`modmex_lambda.stream` is source-first: a source parses a raw AWS Lambda event
into units of work, binds a registry, and runs one or more flavor pipelines.

```text
AWS event source -> Source -> UOWs -> RulesRegistry -> Flavor(s)
```

Use it when one Lambda batch should run several independent reactions while
keeping the rest of the batch moving if one record fails.

Common reactions include:

- publish domain events to EventBridge;
- store and correlate events;
- update DynamoDB materialized views;
- write messages to SNS or SQS;
- write objects to S3;
- execute domain tasks.

### Sources

A source answers “where did this Lambda event come from?” Built-in sources
normalize DynamoDB Streams, Kinesis, S3, SNS, and SQS events.

```python
from modmex_lambda.stream.sources import (
    DynamoDBSource,
    KinesisSource,
    S3Source,
    SnsSource,
    SqsSource,
    dynamodb_source,
    kinesis_source,
    s3_source,
    sns_source,
    sqs_source,
)
```

Class and decorator helpers accept the same runtime options:

```python
handler = KinesisSource(
    registry,
    concurrency=False,
    on_next=on_next,
    on_error=on_error,
    on_completed=on_completed,
    dependency_resolver=dependency_resolver,
).handle
```

`DynamoDBSource` also accepts parser options when table attributes use custom
names:

```python
DynamoDBSource(
    registry,
    parser_options={
        "pk_fn": "pk",
        "sk_fn": "sk",
        "discriminator_fn": "discriminator",
        "event_type_prefix": "ENTITY",
    },
)
```

### Registry And Rules

A registry is the explicit list of flavor instances a source should run:

```python
from modmex_lambda.stream.flavors.cdc import ChangeDataCapture
from modmex_lambda.stream.flavors.materialize import Materialize
from modmex_lambda.stream.rules_registry import RulesRegistry

registry = (
    RulesRegistry()
    .registry(ChangeDataCapture({
        "id": "thing-cdc",
        "event_type": "THING-created",
        "to_event": to_event,
    }))
    .registry(Materialize({
        "id": "thing-materialized",
        "event_type": "thing-created",
        "to_update_request": to_update_request,
    }))
)
```

All built-in flavor rules share:

- `id`: unique pipeline id.
- `event_type`: string, list of strings, or callable matcher.
- `filters`: optional content filters that receive `(uow, rule)`.

### Unit Of Work

Every source creates serializable UOW dictionaries:

```python
{
    "pipeline": "thing-cdc",
    "record": {...},  # original AWS record
    "event": {
        "id": "event-id",
        "type": "thing-created",
        "timestamp": 1548967022000,
        "partition_key": "thing-1",
        "tags": {...},
    },
}
```

DynamoDB stream events also include `event["raw"]` with the mapped `new` and
`old` images.

### Runtime Callbacks

Sources expose lifecycle callbacks that are useful in tests, metrics, and
custom observability:

```python
completed = []
errors = []
items = []

handler = KinesisSource(
    registry,
    concurrency=False,
    on_next=lambda pipeline_id, uow: items.append((pipeline_id, uow)),
    on_error=lambda pipeline_id, error: errors.append((pipeline_id, error)),
    on_completed=lambda pipeline_id: completed.append(pipeline_id),
).handle
```

Use `concurrency=False` in tests when deterministic order matters.

### Publisher Options

Flavors that publish to EventBridge use a shared publisher. Configure it with
`publisher_options`:

```python
ChangeDataCapture(
    {
        "id": "thing-cdc",
        "event_type": "THING-created",
        "to_event": to_event,
    },
    publisher_options={
        "bus_name": "domain-events",
        "source": "things.write-model",
        "batch_size": 10,
    },
)
```

If `bus_name` is omitted, the publisher uses `BUS_NAME`. If `source` is omitted,
it uses `BUS_SRC` or `custom`.

### Shared Dependency Injection

REST handlers and stream handlers can share the same `injector.Injector`. Add
`AwsConnectorsModule` when stream flavors should resolve the built-in AWS
connectors through DI.

```python
from injector import Injector
from modmex_lambda import AwsConnectorsModule, InjectorDependencyResolver

container = Injector([AwsConnectorsModule(), AppModule()])
dependency_resolver = InjectorDependencyResolver(container)

stream_handler = KinesisSource(
    registry,
    dependency_resolver=dependency_resolver,
).handle
```

## Event-Driven Patterns

Use stream flavors as named building blocks for common AWS Lambda event
workflows. Each flavor listens to normalized units of work (`uow`), filters by
rule, and then performs one focused job.

### Change Data Capture

Use `ChangeDataCapture` when a DynamoDB Stream represents changes in your
system of record and you want to publish domain events from those changes.

Typical flow:

```text
DynamoDB table -> DynamoDB Stream -> ChangeDataCapture -> EventBridge
```

For example, an inserted `USER` item can become a `user-created` event. This is
useful when your write model is DynamoDB and other services should react without
calling the writer directly.

```python
from modmex_lambda.stream.flavors.cdc import ChangeDataCapture
from modmex_lambda.stream.rules_registry import RulesRegistry
from modmex_lambda.stream.sources import DynamoDBSource


def to_thing_created(uow):
    thing = uow["event"]["raw"]["new"]
    return {
        "id": thing["id"],
        "type": "thing-created",
        "timestamp": uow["event"]["timestamp"],
        "partition_key": thing["id"],
        "thing": {
            "id": thing["id"],
            "name": thing["name"],
        },
    }


registry = RulesRegistry().registry(
    ChangeDataCapture(
        {
            "id": "thing-cdc",
            "event_type": "THING-created",
            "to_event": to_thing_created,
        },
        publisher_options={
            "bus_name": "domain-events",
            "source": "things.write-model",
        },
    )
)

handler = DynamoDBSource(registry, concurrency=False).handle
```

### Materialize

Use `Materialize` when a service listens to domain events and updates a local
read model or projection.

Typical flow:

```text
EventBridge/Kinesis/SQS -> Materialize -> DynamoDB read model
```

For example, an `order-paid` event can update a customer summary table. You
materialize so queries stay local and fast, and each service owns the model it
needs instead of querying another service synchronously.

```python
from modmex_lambda.persistence.dynamodb import MaterializedViewMixin
from modmex_lambda.stream.flavors.materialize import Materialize
from modmex_lambda.stream.rules_registry import RulesRegistry
from modmex_lambda.stream.sources import KinesisSource


class ThingViewRepository(MaterializedViewMixin):
    discriminator = "thing"


to_update_request = ThingViewRepository.materialized_update_request_mapper()


registry = RulesRegistry().registry(
    Materialize({
        "id": "materialize-thing",
        "event_type": "thing-created",
        "to_update_request": to_update_request,
    })
)

handler = KinesisSource(registry, concurrency=False).handle
```

`MaterializedViewMixin` is a persistence helper for the common DynamoDB case:
copy the entity from `uow["event"][discriminator]`, build a `Key` with
`pk=entity["id"]` and `sk=discriminator`, add stream-compatible fields, and
protect the write with `timestamp_condition()` so older events do not overwrite
newer records. It adds stream-compatible fields such as `discriminator`,
`timestamp`, `deleted`, `latched`, `ttl`, and `awsregion` to the update
expression.

Override the hooks when the event source, key, projection, or enrichment is
different from the default:

```python
from modmex_lambda.persistence.dynamodb import MaterializedViewMixin


class ThingSearchViewRepository(MaterializedViewMixin):
    discriminator = "thing-search"
    materialized_source_name = "thing"

    def materialized_key(self, uow, thing):
        return {
            "pk": thing["tenant_id"],
            "sk": f"thing-search#{thing['id']}",
        }

    def materialized_fields(self, uow, thing):
        return {
            **super().materialized_fields(uow, thing),
            "search_text": f"{thing['name']} {thing['tenant_id']}",
        }
```

Use `DynamoDBUpdateRequestMixin.build_update_request()` directly when you already
have the key and fields but still want the standard `UpdateItem` expression and
timestamp guard.

Use `split_on` and `split_target_field` when one event updates several records,
for example one `order-created` event materializing each order item.

### Control And Orchestration

Use the control pattern when one business process depends on several events
happening over time. It is useful for sagas, process managers, and long-running
coordination without a central synchronous transaction.

The usual pieces are:

- `Collect`: stores incoming events by a correlation key.
- `Correlate`: writes secondary correlation records when one event should be
  findable by another key.
- `Evaluate`: checks collected/correlated events and emits higher-order events
  when a condition is satisfied.

Typical flow:

```text
events -> Collect -> DynamoDB control table -> Evaluate -> EventBridge
                         ^
                         |
                    Correlate
```

For example, an order saga might collect `order-created`,
`payment-authorized`, and `inventory-reserved`. Once `Evaluate` sees the
required events, it emits `order-ready-to-ship`. Downstream services can keep
reacting through EventBridge, SNS, SQS, or Kinesis.

First Lambda: listen to the event stream and collect the events by order id.

```python
from modmex_lambda.stream.flavors.collect import Collect
from modmex_lambda.stream.rules_registry import RulesRegistry
from modmex_lambda.stream.sources import KinesisSource


collect_registry = RulesRegistry().registry(
    Collect({
        "id": "collect-order-events",
        "event_type": ["order-created", "payment-authorized"],
        "correlation_key": "order.id",
        "include_raw": False,
        "expire": "order-correlation-expired",
    })
)

handler = KinesisSource(collect_registry, concurrency=False).handle
```

Second Lambda: consume the DynamoDB stream from the collection table.
`Correlate` writes correlation records and `Evaluate` checks whether the
workflow is ready.

```python
from modmex_lambda.stream.flavors.correlate import Correlate
from modmex_lambda.stream.flavors.evaluate import Evaluate
from modmex_lambda.stream.rules_registry import RulesRegistry
from modmex_lambda.stream.sources import DynamoDBSource


def order_is_ready(uow):
    types = [event["type"] for event in uow["correlated"]]
    return "order-created" in types and "payment-authorized" in types


control_registry = (
    RulesRegistry()
    .registry(Correlate({
        "id": "correlate-order",
        "event_type": ["order-created", "payment-authorized"],
        "correlation_key": "order.id",
        "correlation_key_suffix": "ready",
    }))
    .registry(Evaluate(
        {
            "id": "order-ready",
            "event_type": ["order-created", "payment-authorized"],
            "correlation_key_suffix": "ready",
            "expression": order_is_ready,
            "emit": "order-ready",
        },
        publisher_options={
            "bus_name": "domain-events",
            "source": "orders.control",
        },
    ))
)

handler = DynamoDBSource(control_registry, concurrency=False).handle
```

### Event Hub

EventBridge is a natural hub for domain events. Flavors like
`ChangeDataCapture`, `Evaluate`, and the publisher operator can put events on
the bus; consumers can then use `kinesis_source`, `sqs_source`, `sns_source`, or
`dynamodb_source` depending on the integration shape.

Use SNS when the target contract is topic fan-out and SQS when the target needs
durable queue semantics. Use EventBridge when events are part of the domain
language and should be routed by event type, source, account, or bus.

### Other Flavors

- `Task`: runs arbitrary business logic for matching events and can optionally
  emit a follow-up event.
- `Job`: uses a DynamoDB job record to drive paginated work and emit or update
  per-item results.
- `Expired`: consumes DynamoDB TTL `REMOVE` records and publishes expiration
  events.
- `S3`: writes objects to S3.
- `Sns`: publishes messages to SNS.
- `Update`: queries, gets, and updates DynamoDB records.

`Task` callbacks receive the current `Task` flavor instance. Use `task.rule`
for rule configuration and `task.resolve(...)` for dependencies bound by the
source or registry:

```python
from pydash import get

from modmex_lambda.stream.flavors.task import Task
from modmex_lambda.stream.rules_registry import RulesRegistry
from modmex_lambda.stream.sources import KinesisSource


class ResumeAnalyzerService:
    def analyze(self, application):
        return {
            "application_id": application["id"],
            "confidence": 0.87,
        }


def analyze_resume(uow, task):
    analyzer = task.resolve(ResumeAnalyzerService)
    return analyzer.analyze(get(uow, "event.application"))


registry = RulesRegistry().registry(
    Task({
        "id": "analyze-resume",
        "event_type": "resume-analysis-requested",
        "execute": analyze_resume,
        "emit": lambda uow, task, template: {
            **template,
            "type": "resume-analyzed",
            "application": {
                **get(uow, "event.application"),
                "analysis": uow["result"],
                "pipeline": task.rule["id"],
            },
        },
    })
)

handler = KinesisSource(registry, concurrency=False).handle
```

## Limitations

- OpenAPI/Swagger generation is not implemented.
- Async API Gateway resolver pipelines are not implemented yet.
