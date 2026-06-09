# mypy: ignore-errors
from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from copy import copy
from dataclasses import dataclass, is_dataclass
from typing import Any, Deque, FrozenSet, List, Set, Tuple, Union, Literal, Annotated, get_args, get_origin


from modmex import BaseModel, ValidationError, create_model
from modmex_lambda.validation import ModmexValidator

from modmex_lambda.event_handler.dependencies.types import IncEx, UnionType
    
from modmex import Field as FieldInfo, Undefined
from modmex.fields import UndefinedType


Required = Undefined



sequence_annotation_to_type = {
    Sequence: list,
    List: list,
    list: list,
    Tuple: tuple,
    tuple: tuple,
    Set: set,
    set: set,
    FrozenSet: frozenset,
    frozenset: frozenset,
    Deque: deque,
    deque: deque,
}

sequence_types = tuple(sequence_annotation_to_type.keys())



class ErrorWrapper(Exception):
    pass


@dataclass
class ModelField:
    field_info: FieldInfo
    name: str
    mode: Literal["validation", "serialization"] = "validation"

    @property
    def alias(self) -> str:
        value = self.field_info.alias
        return value if value is not None else self.name

    @property
    def required(self) -> bool:
        return self.field_info.is_required()

    @property
    def default(self) -> Any:
        return self.get_default()

    @property
    def type_(self) -> Any:
        return self.field_info.annotation

    # def __post_init__(self) -> None:
    #     # If the field_info.annotation is already an Annotated type with discriminator metadata,
    #     # use it directly instead of wrapping it again
    #     annotation = self.field_info.annotation
    #     if (
    #         get_origin(annotation) is Annotated
    #         and hasattr(self.field_info, "discriminator")
    #         and self.field_info.discriminator is not None
    #     ):
    #         self._type_adapter: TypeAdapter[Any] = TypeAdapter(annotation)
    #     else:
    #         self._type_adapter: TypeAdapter[Any] = TypeAdapter(
    #             Annotated[annotation, self.field_info],
    #         )

    def get_default(self) -> Any:
        if self.field_info.is_required():
            return None
        return self.field_info.get_default(call_default_factory=True)

    def serialize(
        self,
        value: Any,
        *,
        mode: Literal["json", "python"] = "json",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = True,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> Any:
        return ModmexValidator().serialize(value)

    def validate(
        self,
        value: Any,
        *,
        loc: tuple[int | str, ...] = (),
    ) -> tuple[Any, list[dict[str, Any]] | None]:
        try:
            return (ModmexValidator().validate(value, self.field_info.annotation, list(loc)), None)
        except ValidationError as exc:
            return None, _regenerate_error_with_loc(errors=exc.errors, loc_prefix=())

    def __hash__(self) -> int:
        # Each ModelField is unique for our purposes
        return id(self)


def _normalize_errors(errors: Sequence[Any]) -> list[dict[str, Any]]:
    return errors  # type: ignore[r


def create_body_model(*, fields: Sequence[ModelField], model_name: str) -> type[BaseModel]:
    field_params = {f.name: (f.field_info.annotation, f.field_info) for f in fields}
    model: type[BaseModel] = create_model(model_name, **field_params)
    return model


def is_scalar_field(field: ModelField) -> bool:
    from modmex_lambda.event_handler.dependencies.params import Body

    return field_annotation_is_scalar(field.field_info.annotation) and not isinstance(field.field_info, Body)


def field_annotation_is_complex(annotation: type[Any] | None) -> bool:
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        return any(field_annotation_is_complex(arg) for arg in get_args(annotation))

    return (
        _annotation_is_complex(annotation)
        or _annotation_is_complex(origin)
        # or hasattr(origin, "__pydantic_core_schema__")
        # or hasattr(origin, "__get_pydantic_core_schema__")
    )


def field_annotation_is_scalar(annotation: Any) -> bool:
    return annotation is Ellipsis or not field_annotation_is_complex(annotation)


def field_annotation_is_sequence(annotation: type[Any] | None) -> bool:
    return _annotation_is_sequence(annotation) or _annotation_is_sequence(get_origin(annotation))


def _annotation_is_complex(annotation: type[Any] | None) -> bool:
    return (
        lenient_issubclass(annotation, (BaseModel, Mapping))  # Keep it to UploadFile
        or _annotation_is_sequence(annotation)
        or is_dataclass(annotation)
    )

def get_annotation_from_field_info(annotation: Any, field_info: FieldInfo, field_name: str) -> Any:
    return annotation


def copy_field_info(*, field_info: FieldInfo, annotation: Any) -> FieldInfo:
    # Create a shallow copy of the field_info to preserve its type and all attributes
    new_field = copy(field_info)

    # Recursively extract all metadata from nested Annotated types
    def extract_metadata(ann: Any) -> tuple[Any, list[Any]]:
        """Extract base type and all non-FieldInfo metadata from potentially nested Annotated types."""
        if get_origin(ann) is not Annotated:
            return ann, []

        args = get_args(ann)
        base_type = args[0]
        metadata = list(args[1:])

        # If base type is also Annotated, recursively extract its metadata
        if get_origin(base_type) is Annotated:
            inner_base, inner_metadata = extract_metadata(base_type)
            all_metadata = [m for m in inner_metadata + metadata if not isinstance(m, FieldInfo)]
            return inner_base, all_metadata
        else:
            constraint_metadata = [m for m in metadata if not isinstance(m, FieldInfo)]
            return base_type, constraint_metadata

    # Extract base type and constraints
    base_type, constraints = extract_metadata(annotation)

    # Set the annotation with base type and all constraint metadata
    # Use tuple unpacking for Python 3.10+ compatibility
    if constraints:
        new_field.annotation = Annotated[(base_type, *constraints)]
    else:
        new_field.annotation = base_type

    return new_field


def get_missing_field_error(loc: tuple[str, ...]) -> dict[str, Any]:
    if hasattr(ValidationError, "from_exception_data"):
        error = ValidationError.from_exception_data(
            "Field required",
            [{"type": "missing", "loc": loc, "input": {}}],
        ).errors()[0]
        error["input"] = None
        return error
    return {"type": "missing", "loc": loc, "msg": "Field required", "input": None}


def _annotation_is_sequence(annotation: type[Any] | None) -> bool:
    if lenient_issubclass(annotation, (str, bytes)):
        return False
    return lenient_issubclass(annotation, sequence_types)

def _regenerate_error_with_loc(*, errors: Sequence[Any], loc_prefix: tuple[str | int, ...]) -> list[dict[str, Any]]:
    updated_loc_errors: list[Any] = [
        {**err, "loc": loc_prefix + tuple(err.get("loc", ()))} for err in _normalize_errors(errors)
    ]

    return updated_loc_errors


def lenient_issubclass(cls: Any, class_or_tuple: Any) -> bool:  # pragma: no cover
    try:
        return isinstance(cls, type) and issubclass(cls, class_or_tuple)
    except TypeError:
        return False
