from __future__ import annotations

import inspect
from enum import Enum
from typing import Any, Literal, Annotated, get_args, get_origin

from modmex import BaseModel, FieldInfo, create_model

import modmex_lambda.event_handler.params as public_params
from modmex_lambda.event_handler.dependencies.compat import (
    ModelField,
    Required,
    copy_field_info,
    field_annotation_is_scalar,
    get_annotation_from_field_info,
    lenient_issubclass,
)
from modmex_lambda.event_handler.dependencies.depends import Dependant
from modmex_lambda.event_handler.dependencies.types import CacheKey
from modmex_lambda.event_handler.response import Response


class ParamTypes(Enum):
    query = "query"
    header = "header"
    path = "path"
    cookie = "cookie"


class Param(FieldInfo):  # type: ignore[misc]
    in_ = ParamTypes


class Path(Param):  # type: ignore[misc]
    in_ = ParamTypes.path


class Query(Param):  # type: ignore[misc]
    in_ = ParamTypes.query


class Header(Param):  # type: ignore[misc]
    in_ = ParamTypes.header


class Cookie(Param):  # type: ignore[misc]
    in_ = ParamTypes.cookie


class Body(FieldInfo):  # type: ignore[misc]
    pass


class Form(Body):  # type: ignore[misc]
    pass


class UploadFile:
    """Uploaded file value produced by multipart form parsing."""

    __slots__ = ("content", "content_type", "filename")

    def __init__(self, *, content: bytes, filename: str | None = None, content_type: str | None = None):
        self.content = content
        self.filename = filename
        self.content_type = content_type

    def __len__(self) -> int:
        return len(self.content)

    def __repr__(self) -> str:
        return f"UploadFile(filename={self.filename!r}, content_type={self.content_type!r}, size={len(self.content)})"

    @classmethod
    def _validate(cls, v: Any) -> UploadFile:
        if isinstance(v, cls):
            return v
        raise ValueError(f"Expected UploadFile, got {type(v).__name__}")


class File(Form):  # type: ignore[misc]
    pass


_PUBLIC_PARAM_TO_INTERNAL: dict[type[Any], type[FieldInfo]] = {
    public_params.Body: Body,
    public_params.Query: Query,
    public_params.Path: Path,
    public_params.Header: Header,
    public_params.Cookie: Cookie,
}


def _is_public_param_marker(value: Any) -> bool:
    if isinstance(value, type):
        return issubclass(value, public_params.Param)
    return isinstance(value, public_params.Param)


def _public_param_to_field_info(marker: Any) -> FieldInfo:
    marker_type = marker if isinstance(marker, type) else type(marker)
    alias = None if isinstance(marker, type) else marker.name
    return _PUBLIC_PARAM_TO_INTERNAL[marker_type](alias=alias)


def get_flat_dependant(
    dependant: Dependant,
    visited: list[CacheKey] | None = None,
) -> Dependant:
    visited = visited or []
    visited.append(dependant.cache_key)

    flat = Dependant(
        path_params=dependant.path_params.copy(),
        query_params=dependant.query_params.copy(),
        header_params=dependant.header_params.copy(),
        cookie_params=dependant.cookie_params.copy(),
        body_params=dependant.body_params.copy(),
        path=dependant.path,
    )

    for dep in dependant.dependencies:
        if dep.dependant.cache_key in visited:
            continue
        sub_flat = get_flat_dependant(dep.dependant, visited=visited)
        flat.path_params.extend(sub_flat.path_params)
        flat.query_params.extend(sub_flat.query_params)
        flat.header_params.extend(sub_flat.header_params)
        flat.cookie_params.extend(sub_flat.cookie_params)
        flat.body_params.extend(sub_flat.body_params)

    return flat


def analyze_param(
    *,
    param_name: str,
    annotation: Any,
    value: Any,
    is_path_param: bool,
    is_response_param: bool,
) -> ModelField | None:
    field_info, type_annotation = _resolve_field_info(annotation, value, is_path_param, is_response_param)

    if isinstance(value, FieldInfo):
        if field_info is not None:
            raise AssertionError("Cannot use a FieldInfo as a parameter annotation and pass a FieldInfo as a value")
        field_info = value
        field_info.annotation = type_annotation

    if field_info is None:
        field_info = _default_field_info(type_annotation, value, is_path_param)

    if is_response_param:
        field_info.default = Required

    return _create_model_field(field_info, type_annotation, param_name, is_path_param, is_response_param)


def _resolve_field_info(
    annotation: Any,
    value: Any,
    is_path_param: bool,
    is_response_param: bool,
) -> tuple[FieldInfo | None, Any]:
    if annotation is inspect.Signature.empty:
        return None, Any

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Annotated:
        return _resolve_annotated(annotation, value, is_path_param)
    if _is_public_param_marker(annotation):
        return _field_from_public_marker(annotation, Any, value, is_path_param)
    if origin is Response:
        (inner_type,) = args
        return _resolve_field_info(inner_type, value, False, True)
    if is_response_param and origin is tuple and len(args) == 2:
        inner_type = args[0]
        if get_origin(inner_type) is Annotated:
            return _resolve_annotated(inner_type, value, False)
        return None, inner_type

    return None, annotation


def _field_from_public_marker(
    marker: Any,
    type_annotation: Any,
    value: Any,
    is_path_param: bool,
) -> tuple[FieldInfo, Any]:
    field_info = _public_param_to_field_info(marker)
    field_info.annotation = type_annotation
    _set_field_default(field_info, value, is_path_param)
    return field_info, type_annotation


def _default_field_info(type_annotation: Any, value: Any, is_path_param: bool) -> FieldInfo:
    default = value if value is not inspect.Signature.empty else Required
    if is_path_param:
        return Path(annotation=type_annotation)
    if field_annotation_is_scalar(type_annotation):
        return Query(annotation=type_annotation, default=default)
    return Body(annotation=type_annotation, default=default)


def _resolve_annotated(annotation: Any, value: Any, is_path_param: bool) -> tuple[FieldInfo | None, Any]:
    annotated_args = get_args(annotation)
    type_annotation = annotated_args[0]
    markers: list[FieldInfo] = []
    metadata: list[Any] = []

    for item in annotated_args[1:]:
        marker = _annotation_to_field_info(item)
        if marker is None:
            metadata.append(item)
        else:
            markers.append(marker)

    if len(markers) > 1:
        raise AssertionError("Only one FieldInfo can be used per parameter")

    if metadata:
        type_annotation = Annotated[(type_annotation, *metadata)]

    if not markers:
        return None, type_annotation

    field_info = copy_field_info(field_info=markers[0], annotation=type_annotation)
    _set_field_default(field_info, value, is_path_param)
    return field_info, type_annotation


def _annotation_to_field_info(annotation: Any) -> FieldInfo | None:
    if isinstance(annotation, FieldInfo):
        return annotation
    if isinstance(annotation, type) and issubclass(annotation, FieldInfo):
        return annotation()
    if _is_public_param_marker(annotation):
        return _public_param_to_field_info(annotation)
    return None


def _set_field_default(field_info: FieldInfo, value: Any, is_path_param: bool) -> None:
    if field_info.default not in [None, Required]:
        raise AssertionError("FieldInfo needs to have a default value of None or Required")

    if value is inspect.Signature.empty:
        field_info.default = Required
        return

    if is_path_param:
        raise AssertionError("Cannot use a FieldInfo as a path parameter and pass a value")

    if isinstance(field_info, Header) and isinstance(value, str) and field_info.alias is None:
        field_info.alias = value.lower()
        field_info.default = Required
        return

    field_info.default = value


def create_response_field(
    name: str,
    type_: Any,
    default: Any | None = None,
    field_info: FieldInfo | None = None,
    alias: str | None = None,
    mode: Literal["validation", "serialization"] = "validation",
) -> ModelField:
    field_info = field_info or FieldInfo(annotation=type_, default=default, alias=alias)
    return ModelField(name=name, field_info=field_info, mode=mode)


def _apply_header_model_aliases(field_info: FieldInfo, type_annotation: Any) -> tuple[FieldInfo, Any]:
    if not isinstance(field_info, Header) or not lenient_issubclass(type_annotation, BaseModel):
        return field_info, type_annotation

    header_model = create_model(
        f"{type_annotation.__name__}WithHeaderAliases",
        __base__=type_annotation,
        __config__={"alias_generator": lambda name: name.replace("_", "-")},
    )
    field_info.annotation = header_model
    return field_info, header_model


def _create_model_field(
    field_info: FieldInfo | None,
    type_annotation: Any,
    param_name: str,
    is_path_param: bool,
    is_response_param: bool = False,
) -> ModelField | None:
    if field_info is None:
        return None

    if is_path_param and not isinstance(field_info, Path):
        raise AssertionError("Path parameters must be of type Path")
    if not is_path_param and isinstance(field_info, Param) and getattr(field_info, "in_", None) is None:
        field_info.in_ = ParamTypes.query

    field_info, type_annotation = _apply_header_model_aliases(field_info, type_annotation)
    use_annotation = get_annotation_from_field_info(type_annotation, field_info, param_name)

    return create_response_field(
        name=param_name,
        type_=use_annotation,
        default=field_info.default,
        alias=field_info.alias,
        field_info=field_info,
        mode="serialization" if is_response_param else "validation",
    )
