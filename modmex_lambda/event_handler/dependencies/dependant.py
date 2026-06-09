from __future__ import annotations

import inspect
import re
from typing import Any, Callable, ForwardRef, Union, cast, get_args, get_origin

from modmex import BaseModel

from modmex_lambda.event_handler.dependencies.compat import ModelField, Required, create_body_model, is_scalar_field
from modmex_lambda.event_handler.dependencies.depends import DependencyParam, _get_depends_from_annotation
from modmex_lambda.event_handler.dependencies.params import (
    Body,
    Dependant,
    File,
    Form,
    Param,
    ParamTypes,
    analyze_param,
    create_response_field,
    get_flat_dependant,
)
from modmex_lambda.event_handler.dependencies.types import UnionType
from modmex_lambda.event_handler.request import Request


def add_param_to_fields(*, field: ModelField, dependant: Dependant) -> None:
    field_info = cast(Param, field.field_info)
    param_fields = {
        ParamTypes.path: dependant.path_params,
        ParamTypes.query: dependant.query_params,
        ParamTypes.header: dependant.header_params,
        ParamTypes.cookie: dependant.cookie_params,
    }

    target = param_fields.get(field_info.in_)
    if target is None:
        raise AssertionError(f"Unsupported param type: {field_info.in_}")
    target.append(field)


def resolve_forward_ref_lenient(
    type_hint: Any,
    globalns: dict[str, Any] | None = None,
    localns: dict[str, Any] | None = None,
) -> Any:
    globalns = globalns or {}
    localns = localns or globalns

    if isinstance(type_hint, str):
        try:
            return eval(type_hint, globalns, localns)
        except Exception:
            return ForwardRef(type_hint)

    if isinstance(type_hint, ForwardRef):
        try:
            return eval(type_hint.__forward_arg__, globalns, localns)
        except Exception:
            return type_hint

    return type_hint


def get_typed_annotation(annotation: Any, globalns: dict[str, Any], localns: dict[str, Any] | None = None) -> Any:
    if isinstance(annotation, str):
        return resolve_forward_ref_lenient(ForwardRef(annotation), globalns, localns or globalns)
    return annotation


def get_closure_namespace(call: Callable[..., Any]) -> dict[str, Any]:
    namespace = dict(getattr(call, "__modmex_lambda_localns__", {}) or {})
    closure = getattr(call, "__closure__", None)
    if not closure:
        return namespace

    namespace.update({name: cell.cell_contents for name, cell in zip(call.__code__.co_freevars, closure)})
    return namespace


def get_typed_signature(call: Callable[..., Any]) -> inspect.Signature:
    signature = inspect.signature(call)
    globalns = getattr(call, "__globals__", {})
    localns = {**globalns, **get_closure_namespace(call)}

    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=get_typed_annotation(param.annotation, globalns, localns),
        )
        for param in signature.parameters.values()
    ]

    if signature.return_annotation is inspect.Signature.empty:
        return inspect.Signature(typed_params)

    return_annotation = get_typed_annotation(signature.return_annotation, globalns, localns)
    return inspect.Signature(typed_params, return_annotation=return_annotation)


def get_path_param_names(path: str) -> set[str]:
    return set(re.findall(r"<(\w+)>", path))


def is_request_annotation(annotation: Any) -> bool:
    if annotation is Request:
        return True

    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        return Request in get_args(annotation)

    return False


def get_dependant(
    *,
    path: str,
    call: Callable[..., Any],
    name: str | None = None,
    responses: dict[int, Any] | None = None,
) -> Dependant:
    dependant = Dependant(call=call, name=name, path=path)
    path_param_names = get_path_param_names(path)
    endpoint_signature = get_typed_signature(call)

    for param_name, param in endpoint_signature.parameters.items():
        if is_request_annotation(param.annotation):
            continue

        depends = _get_depends_from_annotation(param.annotation)
        if depends is not None:
            depends = depends.resolve_for_annotation(param.annotation)
            _inherit_local_namespace(parent=call, dependency=depends.dependency)
            dependant.dependencies.append(
                DependencyParam(
                    param_name=param_name,
                    depends=depends,
                    dependant=Dependant(call=depends.dependency)
                    if inspect.isclass(depends.dependency)
                    else get_dependant(path=path, call=depends.dependency),
                ),
            )
            continue

        _add_route_param(
            dependant=dependant,
            param_name=param_name,
            param=param,
            is_path_param=param_name in path_param_names,
        )

    _add_return_annotation(dependant, endpoint_signature)
    return dependant


def _inherit_local_namespace(*, parent: Callable[..., Any], dependency: Callable[..., Any]) -> None:
    if hasattr(dependency, "__modmex_lambda_localns__"):
        return
    setattr(dependency, "__modmex_lambda_localns__", getattr(parent, "__modmex_lambda_localns__", {}))


def _add_route_param(
    *,
    dependant: Dependant,
    param_name: str,
    param: inspect.Parameter,
    is_path_param: bool,
) -> None:
    param_field = analyze_param(
        param_name=param_name,
        annotation=param.annotation,
        value=param.default,
        is_path_param=is_path_param,
        is_response_param=False,
    )
    if param_field is None:
        raise AssertionError(f"Parameter field is None for param: {param_name}")

    if is_body_param(param_field=param_field, is_path_param=is_path_param):
        dependant.body_params.append(param_field)
    else:
        add_param_to_fields(field=param_field, dependant=dependant)


def _add_return_annotation(dependant: Dependant, endpoint_signature: inspect.Signature) -> None:
    if endpoint_signature.return_annotation is inspect.Signature.empty:
        return

    param_field = analyze_param(
        param_name="return",
        annotation=endpoint_signature.return_annotation,
        value=None,
        is_path_param=False,
        is_response_param=True,
    )
    if param_field is None:
        raise AssertionError("Param field is None for return annotation")

    dependant.return_param = param_field


def is_body_param(*, param_field: ModelField, is_path_param: bool) -> bool:
    if is_path_param:
        if not is_scalar_field(field=param_field):
            raise AssertionError("Path params must be of one of the supported types")
        return False

    if is_scalar_field(field=param_field):
        return False
    if isinstance(param_field.field_info, Param):
        return False
    if not isinstance(param_field.field_info, Body):
        raise AssertionError(f"Param: {param_field.name} can only be a request body, use Body()")
    return True


def get_flat_params(dependant: Dependant) -> list[ModelField]:
    flat_dependant = get_flat_dependant(dependant)
    return (
        flat_dependant.path_params
        + flat_dependant.query_params
        + flat_dependant.header_params
        + flat_dependant.cookie_params
    )


def get_body_field(*, dependant: Dependant, name: str) -> ModelField | None:
    flat_dependant = get_flat_dependant(dependant)
    if not flat_dependant.body_params:
        return None

    first_param = flat_dependant.body_params[0]
    if len({param.name for param in flat_dependant.body_params}) == 1 and not getattr(first_param.field_info, "embed", None):
        return first_param

    for param in flat_dependant.body_params:
        setattr(param.field_info, "embed", True)  # noqa: B010

    body_model = create_body_model(fields=flat_dependant.body_params, model_name=f"Body_{name}")
    required = any(field.required for field in flat_dependant.body_params)
    body_field_info, body_field_info_kwargs = get_body_field_info(
        body_model=body_model,
        flat_dependant=flat_dependant,
        required=required,
    )

    return create_response_field(
        name="body",
        type_=body_model,
        default=Required if required else None,
        alias="body",
        field_info=body_field_info(**body_field_info_kwargs),
    )


def get_body_field_info(
    *,
    body_model: type[BaseModel],
    flat_dependant: Dependant,
    required: bool,
) -> tuple[type[Body], dict[str, Any]]:
    body_field_info_kwargs: dict[str, Any] = {"annotation": body_model, "alias": "body"}

    if not required:
        body_field_info_kwargs["default"] = None

    if any(isinstance(field.field_info, File) for field in flat_dependant.body_params):
        body_field_info_kwargs["media_type"] = "multipart/form-data"
    elif any(isinstance(field.field_info, Form) for field in flat_dependant.body_params):
        body_field_info_kwargs["media_type"] = "application/x-www-form-urlencoded"
    else:
        body_param_media_types = [
            field.field_info.media_type
            for field in flat_dependant.body_params
            if isinstance(field.field_info, Body) and hasattr(field.field_info, "media_type")
        ]
        if body_param_media_types and len(set(body_param_media_types)) == 1:
            body_field_info_kwargs["media_type"] = body_param_media_types[0]

    return Body, body_field_info_kwargs
