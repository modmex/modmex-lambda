from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest


def run_import_probe(code: str) -> dict[str, bool]:
    probe = textwrap.dedent(
        f"""
        import json
        import sys

        {code}

        modules = [
            "boto3",
            "injector",
            "pydash",
            "reactivex",
            "opentelemetry",
            "opentelemetry.trace",
            "modmex_lambda.data_classes.cognito_user_pool_event",
            "modmex_lambda.stream.sources.dynamodb",
            "modmex_lambda.stream.sources.kinesis",
            "modmex_lambda.stream.sources.s3",
            "modmex_lambda.stream.sources.sns",
        ]
        print(json.dumps({{module: module in sys.modules for module in modules}}, sort_keys=True))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_root_import_does_not_load_heavy_optional_modules() -> None:
    loaded = run_import_probe("import modmex_lambda")

    assert loaded["boto3"] is False
    assert loaded["injector"] is False
    assert loaded["pydash"] is False
    assert loaded["reactivex"] is False
    assert loaded["opentelemetry"] is False
    assert loaded["opentelemetry.trace"] is False


def test_api_gateway_resolver_import_does_not_load_stream_or_aws_di_modules() -> None:
    loaded = run_import_probe("from modmex_lambda import APIGatewayHttpResolver")

    assert loaded["boto3"] is False
    assert loaded["injector"] is False
    assert loaded["pydash"] is False
    assert loaded["reactivex"] is False
    assert loaded["opentelemetry"] is False
    assert loaded["opentelemetry.trace"] is False


def test_data_class_reexport_only_loads_requested_family() -> None:
    loaded = run_import_probe("from modmex_lambda.data_classes import APIGatewayProxyEventV2")

    assert loaded["modmex_lambda.data_classes.cognito_user_pool_event"] is False


def test_stream_sources_package_does_not_load_all_source_modules() -> None:
    loaded = run_import_probe("import modmex_lambda.stream.sources")

    assert loaded["reactivex"] is False
    assert loaded["modmex_lambda.stream.sources.dynamodb"] is False
    assert loaded["modmex_lambda.stream.sources.kinesis"] is False
    assert loaded["modmex_lambda.stream.sources.s3"] is False
    assert loaded["modmex_lambda.stream.sources.sns"] is False


def test_data_classes_lazy_module_dir_and_unknown_attribute() -> None:
    import modmex_lambda.data_classes as data_classes

    assert "APIGatewayProxyEvent" in dir(data_classes)
    with pytest.raises(AttributeError):
        getattr(data_classes, "UnknownEvent")


def test_event_handler_dependencies_lazy_module_dir_and_unknown_attribute() -> None:
    import modmex_lambda.event_handler.dependencies as dependencies

    assert "Depends" in dir(dependencies)
    assert dependencies.Depends is not None
    with pytest.raises(AttributeError):
        getattr(dependencies, "UnknownDependency")
