from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modmex_lambda.stream.sources.dynamodb import DynamoDBSource, dynamodb_source
    from modmex_lambda.stream.sources.kinesis import KinesisSource, kinesis_source
    from modmex_lambda.stream.sources.s3 import S3Source, s3_source
    from modmex_lambda.stream.sources.sns import SnsSource, sns_source
    from modmex_lambda.stream.sources.sqs import SqsSource, sqs_source

_EXPORTS = {
    "DynamoDBSource": ("modmex_lambda.stream.sources.dynamodb", "DynamoDBSource"),
    "dynamodb_source": ("modmex_lambda.stream.sources.dynamodb", "dynamodb_source"),
    "KinesisSource": ("modmex_lambda.stream.sources.kinesis", "KinesisSource"),
    "kinesis_source": ("modmex_lambda.stream.sources.kinesis", "kinesis_source"),
    "S3Source": ("modmex_lambda.stream.sources.s3", "S3Source"),
    "s3_source": ("modmex_lambda.stream.sources.s3", "s3_source"),
    "SnsSource": ("modmex_lambda.stream.sources.sns", "SnsSource"),
    "sns_source": ("modmex_lambda.stream.sources.sns", "sns_source"),
    "SqsSource": ("modmex_lambda.stream.sources.sqs", "SqsSource"),
    "sqs_source": ("modmex_lambda.stream.sources.sqs", "sqs_source"),
}


__all__ = [
    "DynamoDBSource",
    "KinesisSource",
    "S3Source",
    "SnsSource",
    "SqsSource",
    "dynamodb_source",
    "kinesis_source",
    "s3_source",
    "sns_source",
    "sqs_source",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr = target
    value = getattr(import_module(module_name), attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals().keys(), *__all__])
