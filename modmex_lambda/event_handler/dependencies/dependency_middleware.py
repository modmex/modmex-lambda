from typing import Any, Mapping, MutableMapping, Sequence, Union
from typing_extensions import get_args, get_origin

from modmex import BaseModel, FieldInfo
from modmex_lambda.exceptions import RequestValidationError
from modmex_lambda.event_handler.middlewares import IMiddleware, NextMiddleware
from modmex_lambda.event_handler.dependencies.compat import (
    _normalize_errors,
    _regenerate_error_with_loc,
    field_annotation_is_sequence,
    get_missing_field_error,
    lenient_issubclass,
    is_scalar_field
)
from modmex_lambda.event_handler.types import IApiGatewayResolver
from modmex_lambda.event_handler.routing import IRoute

from modmex_lambda.event_handler.dependencies.params import ModelField, Param, UploadFile
from modmex_lambda.event_handler.dependencies.types import UnionType
from modmex_lambda.event_handler.response import Response


class DependencyMiddleware(IMiddleware):
    def _get_body(self, app: IApiGatewayResolver) -> Any:
        return app.current_event.json_body

    def handler(self, app: IApiGatewayResolver, next_middleware: NextMiddleware) -> Response:
        route: IRoute = app.context.get("_route")
        values: dict[str, Any] = {}
        errors: list[Any] = []

        param_sources = (
            (route.dependant.path_params, app.context.get("_route_args")),
            (
                route.dependant.query_params,
                _normalize_multi_params(app.current_event.resolved_query_string_parameters, route.dependant.query_params),
            ),
            (
                route.dependant.header_params,
                _normalize_multi_params(app.current_event.resolved_headers_field, route.dependant.header_params),
            ),
            (route.dependant.cookie_params, getattr(app.current_event, "resolved_cookies_field", {})),
        )

        for params, received_params in param_sources:
            param_values, param_errors = _request_params_to_args(params, received_params)
            values.update(param_values)
            errors.extend(param_errors)

        if route.dependant.body_params:
            body_values, body_errors = _request_body_to_args(
                required_params=route.dependant.body_params,
                received_body=self._get_body(app),
            )
            values.update(body_values)
            errors.extend(body_errors)

        if errors:
            raise RequestValidationError(_normalize_errors(errors))

        app.context["_route_args"] = values
        return next_middleware(app)



def _request_params_to_args(
    required_params: Sequence[ModelField],
    received_params: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Convert the request params to a dictionary of values using validation, and returns a list of errors.
    """
    values: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []

    for field in required_params:
        field_info = field.field_info

        # To ensure early failure, we check if it's not an instance of Param.
        if not isinstance(field_info, Param):
            raise AssertionError(f"Expected Param field_info, got {field_info}")

        loc = (field_info.in_.value, field.alias)
        value = received_params.get(field.alias)

        # If we don't have a value, see if it's required or has a default
        if value is None:
            _handle_missing_field_value(field, values, errors, loc)
            continue

        # Finally, validate the value
        values[field.name] = _validate_field(field=field, value=value, loc=loc, existing_errors=errors)

    return values, errors


def _request_body_to_args(
    required_params: list[ModelField],
    received_body: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Convert the request body to a dictionary of values using validation, and returns a list of errors.
    """
    values: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []

    received_body, field_alias_omitted = _get_embed_body(
        field=required_params[0],
        required_params=required_params,
        received_body=received_body,
    )

    for field in required_params:
        loc = _get_body_field_location(field, field_alias_omitted)
        value = _extract_field_value_from_body(field, received_body, loc, errors)

        # If we don't have a value, see if it's required or has a default
        if value is None:
            _handle_missing_field_value(field, values, errors, loc)
            continue

        value = _normalize_field_value(value=value, field_info=field.field_info)

        # UploadFile objects bypass Pydantic validation — they're already constructed
        if isinstance(value, UploadFile):
            values[field.name] = value
        else:
            values[field.name] = _validate_field(field=field, value=value, loc=loc, existing_errors=errors)

    return values, errors


def _get_body_field_location(field: ModelField, field_alias_omitted: bool) -> tuple[str, ...]:
    """Get the location tuple for a body field based on whether the field alias is omitted."""
    if field_alias_omitted:
        return ("body",)
    return ("body", field.alias)


def _extract_field_value_from_body(
    field: ModelField,
    received_body: dict[str, Any] | None,
    loc: tuple[str, ...],
    errors: list[dict[str, Any]],
) -> Any | None:
    """Extract field value from the received body, handling potential AttributeError."""
    if received_body is None:
        return None

    try:
        return received_body.get(field.alias)
    except AttributeError:
        errors.append(get_missing_field_error(loc))
        return None


def _handle_missing_field_value(
    field: ModelField,
    values: dict[str, Any],
    errors: list[dict[str, Any]],
    loc: tuple[str, ...],
) -> None:
    """Handle the case when a field value is missing."""
    if field.required:
        errors.append(get_missing_field_error(loc))
    else:
        values[field.name] = field.get_default()


def _is_or_contains_sequence(annotation: Any) -> bool:
    """
    Check if annotation is a sequence or Union/RootModel containing a sequence.

    This function handles complex type annotations like:
    - List[Model] - direct sequence
    - Union[Model, List[Model]] - checks if any Union member is a sequence
    - Optional[List[Model]] - Union[List[Model], None]
    - RootModel[List[Model]] - checks if the RootModel wraps a sequence
    - Optional[RootModel[List[Model]]] - Union member that is a RootModel
    - RootModel[Union[Model, List[Model]]] - RootModel wrapping a Union with a sequence
    """
    # Direct sequence check
    if field_annotation_is_sequence(annotation):
        return True

    # Check Union members — recurse so we catch RootModel inside Union
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        for arg in get_args(annotation):
            if _is_or_contains_sequence(arg):
                return True

    # Check if it's a RootModel wrapping a sequence (or Union containing a sequence)
    if lenient_issubclass(annotation, BaseModel) and getattr(annotation, "__pydantic_root_model__", False):
        if hasattr(annotation, "model_fields") and "root" in annotation.model_fields:
            root_annotation = annotation.model_fields["root"].annotation
            return _is_or_contains_sequence(root_annotation)

    return False


def _normalize_field_value(value: Any, field_info: FieldInfo) -> Any:
    """Normalize field value, converting lists to single values for non-sequence fields."""
    return _normalize_value(value=value, annotation=field_info.annotation)


def _normalize_value(value: Any, annotation: Any) -> Any:
    if isinstance(value, UploadFile) and annotation is bytes:
        return value.content

    if _is_or_contains_sequence(annotation):
        return value

    if isinstance(value, list) and value:
        return value[0]

    return value


def _validate_field(
    *,
    field: ModelField,
    value: Any,
    loc: tuple[str, ...],
    existing_errors: list[dict[str, Any]],
):
    """
    Validate a field, and append any errors to the existing_errors list.
    """
    validated_value, errors = field.validate(value=value, loc=loc)

    if isinstance(errors, list):
        processed_errors = _regenerate_error_with_loc(errors=errors, loc_prefix=())
        existing_errors.extend(processed_errors)
    elif errors:
        existing_errors.append(errors)

    return validated_value


def _get_embed_body(
    *,
    field: ModelField,
    required_params: list[ModelField],
    received_body: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, bool]:
    field_info = field.field_info
    embed = getattr(field_info, "embed", None)

    # If the field is an embed, and the field alias is omitted, we need to wrap the received body in the field alias.
    field_alias_omitted = len(required_params) == 1 and not embed
    if field_alias_omitted:
        received_body = {field.alias: received_body}

    return received_body, field_alias_omitted


def _normalize_multi_params(
    input_dict: MutableMapping[str, Any],
    params: Sequence[ModelField],
) -> MutableMapping[str, Any]:
    for param in params:
        if is_scalar_field(param):
            _process_scalar_param(input_dict, param)
        elif lenient_issubclass(param.field_info.annotation, BaseModel):
            _process_model_param(input_dict, param)
    return input_dict


def _process_scalar_param(input_dict: MutableMapping[str, Any], param: ModelField) -> None:
    try:
        value = input_dict[param.alias]
        if isinstance(value, list) and len(value) == 1:
            input_dict[param.alias] = value[0]
    except KeyError:
        pass


def _process_model_param(input_dict: MutableMapping[str, Any], param: ModelField) -> None:
    model_class = param.field_info.annotation

    model_data = {}
    for field_name, field_alias, annotation in _iter_model_fields(model_class):
        value = _get_param_value(input_dict, field_alias, field_name, model_class)
        if value is not None:
            model_data[field_alias] = _normalize_value(value=value, annotation=annotation)

    input_dict[param.alias] = model_data


def _iter_model_fields(model_class: type[BaseModel]):
    model_fields = getattr(model_class, "model_fields", None)
    if model_fields:
        for field_name, field_info in model_fields.items():
            yield field_name, field_info.alias or field_name, field_info.annotation
        return

    alias_generator = getattr(model_class, "model_config", {}).get("alias_generator")
    for field in getattr(model_class, "__modmex_fields__", ()):
        field_alias = alias_generator(field.name) if alias_generator else field.name
        yield field.name, field_alias, field.type


def _get_param_value(
    input_dict: MutableMapping[str, Any],
    field_alias: str,
    field_name: str,
    model_class: type[BaseModel],
) -> Any:
    value = input_dict.get(field_alias)
    if value is not None:
        return value

    model_config = getattr(model_class, "model_config", {})
    if model_config.get("validate_by_name") or model_config.get("populate_by_name"):
        value = input_dict.get(field_name)

    return value


def _extract_multipart_boundary(content_type: str) -> str | None:
    """Extract the boundary string from a multipart/form-data content-type header."""
    for segment in content_type.split(";"):
        stripped = segment.strip()
        if stripped.startswith("boundary="):
            boundary = stripped[len("boundary=") :]
            # Remove optional quotes around boundary
            if boundary.startswith('"') and boundary.endswith('"'):
                boundary = boundary[1:-1]
            return boundary
    return None


def _parse_multipart_body(body: bytes, boundary: str) -> dict[str, Any]:
    """
    Parse a multipart/form-data body into a dict of field names to values.

    File fields get bytes values; regular form fields get string values.
    Multiple values for the same field name are collected into lists.
    """
    delimiter = f"--{boundary}".encode()
    end_delimiter = f"--{boundary}--".encode()

    result: dict[str, Any] = {}

    # Split body by the boundary delimiter
    raw_parts = body.split(delimiter)

    for raw_part in raw_parts:
        # Skip the preamble (before first boundary) and epilogue (after closing boundary)
        if not raw_part or raw_part.strip() == b"" or raw_part.strip() == b"--":
            continue

        # Remove the end delimiter marker if present
        chunk = raw_part
        if chunk.endswith(end_delimiter):
            chunk = chunk[: -len(end_delimiter)]

        # Strip leading \r\n
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]

        # Strip trailing \r\n
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]

        # Split headers from body at the double CRLF
        header_end = chunk.find(b"\r\n\r\n")
        if header_end == -1:
            continue

        header_section = chunk[:header_end].decode("utf-8")
        body_section = chunk[header_end + 4 :]

        # Parse Content-Disposition to get the field name and optional filename
        field_name = None
        filename = None
        content_type_header = None

        for header_line in header_section.split("\r\n"):
            header_lower = header_line.lower()
            if header_lower.startswith("content-disposition:"):
                field_name = _extract_header_param(header_line, "name")
                filename = _extract_header_param(header_line, "filename")
            elif header_lower.startswith("content-type:"):
                content_type_header = header_line.split(":", 1)[1].strip()

        if field_name is None:
            continue

        # If it has a filename, it's a file upload — wrap as UploadFile
        # Otherwise it's a regular form field — decode to string
        if filename is not None:
            value: Any = UploadFile(content=body_section, filename=filename, content_type=content_type_header)
        else:
            value = body_section.decode("utf-8")

        # Collect multiple values for same field name into a list
        if field_name in result:
            existing = result[field_name]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[field_name] = [existing, value]
        else:
            result[field_name] = value

    return result


def _extract_header_param(header_line: str, param_name: str) -> str | None:
    """Extract a parameter value from a header line (e.g., name="file" from Content-Disposition)."""
    search = f'{param_name}="'
    idx = header_line.find(search)
    if idx == -1:
        return None
    start = idx + len(search)
    end = header_line.find('"', start)
    if end == -1:
        return None
    return header_line[start:end]


__all__ = ["DependencyMiddleware"]
