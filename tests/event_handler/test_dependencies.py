from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Annotated, Any

import pytest
from modmex import BaseModel, Field as FieldInfo, ValidationError

from modmex_lambda.data_classes.api_gateway_proxy_event import APIGatewayProxyEventV2
from modmex_lambda.event_handler.dependencies import compat
from modmex_lambda.event_handler.dependencies.compat import ModelField, Required
from modmex_lambda.event_handler.dependencies.dependant import (
    add_param_to_fields,
    get_body_field,
    get_body_field_info,
    get_dependant,
    get_flat_params,
    get_path_param_names,
    get_typed_annotation,
    get_typed_signature,
    is_body_param,
    is_request_annotation,
    resolve_forward_ref_lenient,
)
from modmex_lambda.event_handler.dependencies.dependency_middleware import (
    DependencyMiddleware,
    _extract_header_param,
    _extract_multipart_boundary,
    _get_embed_body,
    _normalize_field_value,
    _normalize_multi_params,
    _parse_multipart_body,
    _request_body_to_args,
    _request_params_to_args,
)
from modmex_lambda.event_handler.dependencies.depends import (
    Dependant,
    DependencyParam,
    DependencyResolutionError,
    Depends,
    build_dependency_tree,
    solve_dependencies,
)
from modmex_lambda.event_handler.dependencies.params import (
    Body,
    Cookie,
    File,
    Form,
    Header,
    Param,
    ParamTypes,
    Path,
    Query,
    UploadFile,
    analyze_param,
    create_response_field,
    get_flat_dependant,
)
from modmex_lambda.event_handler.exceptions import RequestValidationError
from modmex_lambda.event_handler.request import Request
from modmex_lambda.event_handler.response import Response
from modmex_lambda.event_handler import params as public_params
from tests.conftest import http_v2_event


class Payload:
    def __init__(self, name: str, count: int = 1) -> None:
        self.name = name
        self.count = int(count)


class HeaderModel(BaseModel):
    x_tenant_id: str


CALLS = {"token": 0, "counter": 0}


def cached_token() -> str:
    CALLS["token"] += 1
    return "token"


def request_tenant(request: Request) -> str:
    return request.headers["x-tenant-id"]


def cached_repo(
    token_value: Annotated[str, Depends(cached_token)],
    tenant_id: Annotated[str, Depends(request_tenant)],
) -> str:
    return f"{tenant_id}:{token_value}"


def endpoint_with_cached_dependencies(
    first: Annotated[str, Depends(cached_repo)],
    second: Annotated[str, Depends(cached_repo)],
) -> None:
    return None


def uncached_counter() -> int:
    CALLS["counter"] += 1
    return CALLS["counter"]


def endpoint_with_uncached_dependencies(
    first: Annotated[int, Depends(uncached_counter, use_cache=False)],
    second: Annotated[int, Depends(uncached_counter, use_cache=False)],
) -> None:
    return None


def broken_dependency() -> str:
    raise RuntimeError("boom")


def endpoint_with_broken_dependency(value: Annotated[str, Depends(broken_dependency)]) -> None:
    return None


def _field(
    name: str,
    annotation: Any,
    marker: Any,
    *,
    default: Any = inspect.Signature.empty,
    is_path_param: bool = False,
) -> ModelField:
    return analyze_param(
        param_name=name,
        annotation=Annotated[annotation, marker],
        value=default,
        is_path_param=is_path_param,
        is_response_param=False,
    )


def test_depends_rejects_non_callable_and_extracts_annotated_dependency() -> None:
    def dep() -> str:
        return "token"

    with pytest.raises(DependencyResolutionError, match="requires a callable"):
        Depends("not-callable")

    annotation = Annotated[str, Depends(dep)]
    assert build_dependency_tree(lambda value: None).dependencies == []
    assert compat._normalize_errors([{"loc": ("x",), "type": "missing"}]) == [{"loc": ("x",), "type": "missing"}]


def test_solve_dependencies_supports_cache_overrides_request_and_errors() -> None:
    CALLS["token"] = 0
    event = APIGatewayProxyEventV2(http_v2_event("GET", "/items", headers={"x-tenant-id": "mx"}))
    request = Request(route_path="/items", path_parameters={}, current_event=event)

    values = solve_dependencies(dependant=build_dependency_tree(endpoint_with_cached_dependencies), request=request)

    assert values == {"first": "mx:token", "second": "mx:token"}
    assert CALLS["token"] == 1

    overridden = solve_dependencies(
        dependant=build_dependency_tree(endpoint_with_cached_dependencies),
        request=request,
        dependency_overrides={cached_token: lambda: "override"},
    )
    assert overridden == {"first": "mx:override", "second": "mx:override"}

    with pytest.raises(DependencyResolutionError, match="Failed to resolve dependency 'broken_dependency'"):
        solve_dependencies(dependant=build_dependency_tree(endpoint_with_broken_dependency))


def test_solve_dependencies_honors_use_cache_false() -> None:
    CALLS["counter"] = 0

    assert solve_dependencies(dependant=build_dependency_tree(endpoint_with_uncached_dependencies)) == {
        "first": 1,
        "second": 2,
    }


def test_dependant_building_resolves_forward_refs_request_params_dependencies_and_return() -> None:
    LocalPayload = Payload

    def token() -> str:
        return "token"

    def endpoint(
        item_id: int,
        payload: "LocalPayload",
        request: Request | None,
        token_value: Annotated[str, Depends(token)],
    ) -> Payload:
        return payload

    dependant = get_dependant(path="/items/<item_id>", call=endpoint, name="endpoint")

    assert get_path_param_names("/items/<item_id>/comments/<comment_id>") == {"item_id", "comment_id"}
    assert dependant.name == "endpoint"
    assert dependant.path == "/items/<item_id>"
    assert [field.name for field in dependant.path_params] == ["item_id"]
    assert [field.name for field in dependant.query_params] == ["payload", "token_value"]
    assert dependant.dependencies == []
    assert dependant.return_param is not None
    assert is_request_annotation(Request)
    assert is_request_annotation(Request | None)
    assert not is_request_annotation(str)
    assert get_typed_annotation("LocalPayload", endpoint.__globals__, {"LocalPayload": LocalPayload}) is Payload
    assert get_typed_signature(endpoint).return_annotation is not inspect.Signature.empty
    assert resolve_forward_ref_lenient("MissingType", {}, {}).__forward_arg__ == "MissingType"


def test_dependant_infers_angle_bracket_path_parameters_without_explicit_marker() -> None:
    def endpoint(item_id: int) -> None:
        return None

    dependant = get_dependant(path="/items/<item_id>", call=endpoint)

    assert [field.name for field in dependant.path_params] == ["item_id"]
    assert dependant.query_params == []


def test_params_analyze_param_public_markers_defaults_and_errors() -> None:
    query = analyze_param(
        param_name="limit",
        annotation=public_params.Query[int],
        value=public_params.Query(name="limit"),
        is_path_param=False,
        is_response_param=False,
    )
    header = _field("tenant_id", str, Header(), default="x-tenant-id")
    path = _field("item_id", int, Path(), is_path_param=True)
    body = _field("payload", Payload, Body())
    cookie = _field("session", str, Cookie())
    inferred_body = analyze_param(
        param_name="payload",
        annotation=Payload,
        value=inspect.Signature.empty,
        is_path_param=False,
        is_response_param=False,
    )
    inferred_query = analyze_param(
        param_name="limit",
        annotation=int,
        value=10,
        is_path_param=False,
        is_response_param=False,
    )

    assert query.alias == "limit"
    assert header.alias == "x-tenant-id"
    assert path.required is True
    assert isinstance(body.field_info, Body)
    assert isinstance(cookie.field_info, Cookie)
    assert isinstance(inferred_body.field_info, Query)
    assert isinstance(inferred_query.field_info, Query)
    assert inferred_query.default == 10

    with pytest.raises(AssertionError, match="Cannot use a FieldInfo"):
        analyze_param(
            param_name="limit",
            annotation=Annotated[int, Query()],
            value=Query(),
            is_path_param=False,
            is_response_param=False,
        )

    with pytest.raises(AssertionError, match="path parameter"):
        analyze_param(
            param_name="item_id",
            annotation=Annotated[int, Path()],
            value=1,
            is_path_param=True,
            is_response_param=False,
        )


def test_params_analyze_param_supports_public_marker_classes_response_types_and_header_models() -> None:
    cookie = analyze_param(
        param_name="session",
        annotation=public_params.Cookie,
        value=inspect.Signature.empty,
        is_path_param=False,
        is_response_param=False,
    )
    response = analyze_param(
        param_name="return",
        annotation=Response[Payload],
        value=inspect.Signature.empty,
        is_path_param=False,
        is_response_param=True,
    )
    tuple_response = analyze_param(
        param_name="return",
        annotation=tuple[Annotated[Payload, Body()], int],
        value=inspect.Signature.empty,
        is_path_param=False,
        is_response_param=True,
    )
    class_marker_body = analyze_param(
        param_name="payload",
        annotation=Annotated[Payload, Body],
        value=inspect.Signature.empty,
        is_path_param=False,
        is_response_param=False,
    )
    header_model = analyze_param(
        param_name="headers",
        annotation=Annotated[HeaderModel, Header()],
        value=inspect.Signature.empty,
        is_path_param=False,
        is_response_param=False,
    )

    assert isinstance(cookie.field_info, Cookie)
    assert cookie.required is True
    assert isinstance(response.field_info, Query)
    assert response.type_ is Payload
    assert response.mode == "serialization"
    assert isinstance(tuple_response.field_info, Body)
    assert tuple_response.required is True
    assert isinstance(class_marker_body.field_info, Body)
    assert header_model.field_info.annotation.__name__ == "HeaderModelWithHeaderAliases"
    assert header_model.field_info.annotation.model_config["alias_generator"]("x_tenant_id") == "x-tenant-id"

    with pytest.raises(AssertionError, match="Only one FieldInfo"):
        analyze_param(
            param_name="payload",
            annotation=Annotated[Payload, Body(), Query()],
            value=inspect.Signature.empty,
            is_path_param=False,
            is_response_param=False,
        )

    with pytest.raises(AssertionError, match="default value"):
        analyze_param(
            param_name="limit",
            annotation=Annotated[int, Query(default=1)],
            value=inspect.Signature.empty,
            is_path_param=False,
            is_response_param=False,
        )

    with pytest.raises(AssertionError, match="Path parameters"):
        analyze_param(
            param_name="item_id",
            annotation=Annotated[int, Query()],
            value=inspect.Signature.empty,
            is_path_param=True,
            is_response_param=False,
        )


def test_flat_dependant_body_field_and_param_classification() -> None:
    parent = Dependant(call=lambda: None, path="/items")
    child = Dependant(call=lambda: None)
    parent.dependencies.append(
        DependencyParam(param_name="dep", depends=Depends(lambda: None), dependant=child),
    )
    parent.path_params.append(_field("item_id", int, Path(), is_path_param=True))
    parent.query_params.append(_field("limit", int, Query(), default=10))
    child.header_params.append(_field("tenant_id", str, Header(), default="x-tenant-id"))
    child.body_params.append(_field("payload", Payload, Body()))

    flat = get_flat_dependant(parent)

    assert [field.name for field in get_flat_params(parent)] == ["item_id", "limit", "tenant_id"]
    assert [field.name for field in flat.body_params] == ["payload"]
    assert get_body_field(dependant=parent, name="Endpoint").name == "payload"
    assert is_body_param(param_field=child.body_params[0], is_path_param=False)
    assert not is_body_param(param_field=parent.query_params[0], is_path_param=False)
    assert not is_body_param(param_field=parent.path_params[0], is_path_param=True)

    with pytest.raises(AssertionError, match="Path params"):
        is_body_param(param_field=_field("payload", Payload, Body()), is_path_param=True)

    unsupported = create_response_field("bad", str, field_info=Param(annotation=str))
    unsupported.field_info.in_ = object()
    with pytest.raises(AssertionError, match="Unsupported param type"):
        add_param_to_fields(field=unsupported, dependant=Dependant())


def test_body_field_info_for_file_form_and_json_body_models() -> None:
    file_dependant = Dependant(body_params=[_field("upload", UploadFile, File())])
    form_dependant = Dependant(body_params=[_field("name", str, Form())])
    json_dependant = Dependant(body_params=[_field("payload", Payload, Body())])

    file_model = compat.create_body_model(fields=file_dependant.body_params, model_name="FileBody")
    form_model = compat.create_body_model(fields=form_dependant.body_params, model_name="FormBody")
    json_model = compat.create_body_model(fields=json_dependant.body_params, model_name="JsonBody")
    setattr(json_dependant.body_params[0].field_info, "media_type", "application/json")

    assert get_body_field_info(body_model=file_model, flat_dependant=file_dependant, required=True)[1]["media_type"] == (
        "multipart/form-data"
    )
    assert get_body_field_info(body_model=form_model, flat_dependant=form_dependant, required=True)[1]["media_type"] == (
        "application/x-www-form-urlencoded"
    )
    assert get_body_field_info(body_model=json_model, flat_dependant=json_dependant, required=True)[1]["media_type"]


def test_request_params_to_args_validation_defaults_and_errors() -> None:
    limit = _field("limit", int, Query(), default=10)
    required = _field("name", str, Query())

    values, errors = _request_params_to_args([limit, required], {"name": "Ada"})
    assert values == {"limit": 10, "name": "Ada"}
    assert errors == []

    bad_values, bad_errors = _request_params_to_args([required, _field("age", int, Query())], {"age": "bad"})
    assert bad_values == {"age": None}
    assert bad_errors

    not_param = create_response_field("value", int, field_info=FieldInfo(annotation=int))
    with pytest.raises(AssertionError, match="Expected Param"):
        _request_params_to_args([not_param], {})


def test_request_body_to_args_embed_upload_file_bytes_and_non_mapping_errors() -> None:
    payload_field = _field("payload", Payload, Body())
    name_field = _field("name", str, Body())
    age_field = _field("age", int, Body())
    file_field = _field("upload", UploadFile, File())
    bytes_field = _field("content", bytes, File())

    values, errors = _request_body_to_args([payload_field], {"name": "Ada", "count": "2"})
    assert values["payload"].name == "Ada"
    assert values["payload"].count == 2
    assert errors == []

    embedded_values, embedded_errors = _request_body_to_args(
        [name_field],
        {"name": "Ada"},
    )
    assert embedded_values == {"name": None}
    assert embedded_errors

    upload = UploadFile(content=b"hello", filename="hello.txt", content_type="text/plain")
    file_values, file_errors = _request_body_to_args([file_field], upload)
    assert file_values == {"upload": upload}
    assert file_errors == []

    bytes_values, bytes_errors = _request_body_to_args([bytes_field], upload)
    assert bytes_values == {"content": b"hello"}
    assert bytes_errors == []

    _, non_mapping_errors = _request_body_to_args([name_field, age_field], "not-a-dict")
    assert non_mapping_errors

    assert _get_embed_body(field=name_field, required_params=[name_field, payload_field], received_body={}) == ({}, False)


def test_normalize_multi_params_model_and_scalar_values() -> None:
    class LegacyHeaderModel(BaseModel):
        x_tenant_id: str

    scalar = _field("limit", int, Query())
    model = ModelField(name="headers", field_info=Header(annotation=LegacyHeaderModel, alias="headers"))
    LegacyHeaderModel.model_fields = {"x_tenant_id": SimpleNamespace(alias=None, annotation=str)}
    LegacyHeaderModel.model_config = {}
    params = {"limit": ["1"], "x_tenant_id": ["mx"]}

    normalized = _normalize_multi_params(params, [scalar, model])

    assert normalized["limit"] == "1"
    assert normalized["headers"] == {"x_tenant_id": "mx"}


def test_multipart_helpers_parse_fields_files_repeated_values_and_boundaries() -> None:
    body = (
        b"--abc\r\n"
        b'Content-Disposition: form-data; name="name"\r\n\r\n'
        b"Ada\r\n"
        b"--abc\r\n"
        b'Content-Disposition: form-data; name="file"; filename="hello.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\n"
        b"hello\r\n"
        b"--abc\r\n"
        b'Content-Disposition: form-data; name="name"\r\n\r\n'
        b"Lovelace\r\n"
        b"--abc--\r\n"
    )

    parsed = _parse_multipart_body(body, "abc")

    assert _extract_multipart_boundary('multipart/form-data; boundary="abc"') == "abc"
    assert _extract_multipart_boundary("application/json") is None
    assert _extract_header_param('Content-Disposition: form-data; name="file"', "name") == "file"
    assert _extract_header_param("Content-Disposition: form-data", "name") is None
    assert parsed["name"] == ["Ada", "Lovelace"]
    assert parsed["file"].filename == "hello.txt"
    assert parsed["file"].content == b"hello"
    assert parsed["file"].content_type == "text/plain"
    assert len(parsed["file"]) == 5
    assert repr(parsed["file"]) == "UploadFile(filename='hello.txt', content_type='text/plain', size=5)"
    assert UploadFile._validate(parsed["file"]) is parsed["file"]
    with pytest.raises(ValueError, match="Expected UploadFile"):
        UploadFile._validate(b"raw")


def test_dependency_middleware_validates_event_params_and_updates_route_args() -> None:
    def endpoint(
        item_id: Annotated[int, public_params.Path()],
        notify: Annotated[bool, public_params.Query()],
        tenant_id: Annotated[str, public_params.Header(name="x-tenant-id")],
        headers: Annotated[HeaderModel, public_params.Header()],
        session: Annotated[str, public_params.Cookie()],
        payload: Annotated[Payload, public_params.Body()],
    ) -> None:
        return None

    dependant = get_dependant(path="/items/<item_id>", call=endpoint)
    app = SimpleNamespace(
        current_event=APIGatewayProxyEventV2(
            http_v2_event(
                "PUT",
                "/items/42",
                headers={"x-tenant-id": "mx"},
                query={"notify": "true"},
                body={"name": "Ada", "count": "3"},
            ),
        ),
        context={
            "_route": SimpleNamespace(dependant=dependant),
            "_route_args": {"item_id": "42"},
        },
    )

    def next_middleware(next_app):
        return Response(status_code=200, body=next_app.context["_route_args"])

    response = DependencyMiddleware().handler(app, next_middleware)

    assert response.body["item_id"] == 42
    assert response.body["notify"] is True
    assert response.body["tenant_id"] == "mx"
    assert response.body["headers"].x_tenant_id == "mx"
    assert response.body["session"] == "abc"
    assert response.body["payload"].name == "Ada"
    assert response.body["payload"].count == 3


def test_dependency_middleware_raises_request_validation_error() -> None:
    def endpoint(item_id: Annotated[int, public_params.Path()]) -> None:
        return None

    dependant = get_dependant(path="/items/<item_id>", call=endpoint)
    app = SimpleNamespace(
        current_event=APIGatewayProxyEventV2(http_v2_event("GET", "/items/bad")),
        context={
            "_route": SimpleNamespace(dependant=dependant),
            "_route_args": {"item_id": "bad"},
        },
    )

    with pytest.raises(RequestValidationError) as exc_info:
        DependencyMiddleware().handler(app, lambda _: Response(status_code=200))

    assert exc_info.value.errors()


def test_compat_model_field_copy_sequences_missing_errors_and_validation() -> None:
    field_info = FieldInfo(annotation=Annotated[int, "meta"], default=Required, alias="value")
    field = ModelField(name="value", field_info=field_info)

    assert field.alias == "value"
    assert field.required is True
    assert field.default is None
    assert field.type_ is field_info.annotation
    assert field.serialize(HeaderModel(x_tenant_id="mx")) == {"x_tenant_id": "mx"}
    int_field_info = FieldInfo(default=Required, alias="value")
    int_field_info.annotation = int
    int_field = ModelField(name="value", field_info=int_field_info)
    assert int_field.validate("1", loc=("query", "value")) == (1, None)
    assert field.validate("bad", loc=("query", "value"))[1]
    assert isinstance(hash(field), int)
    assert compat.field_annotation_is_sequence(list[int])
    assert not compat.field_annotation_is_sequence(str)
    assert compat.field_annotation_is_scalar(int)
    assert compat.field_annotation_is_complex(HeaderModel)
    assert compat.field_annotation_is_complex(int | HeaderModel)
    assert compat.get_annotation_from_field_info(int, field_info, "value") is int
    with pytest.raises(TypeError):
        compat.copy_field_info(field_info=field_info, annotation=Annotated[int, "meta"])
    assert compat.get_missing_field_error(("query", "value"))["type"] == "missing"
    assert compat._regenerate_error_with_loc(errors=[{"loc": ("value",), "type": "int"}], loc_prefix=("query",)) == [
        {"loc": ("query", "value"), "type": "int"},
    ]
