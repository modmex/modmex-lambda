from __future__ import annotations

from modmex_lambda.event_handler.exception_handler import ExceptionHandlerManager


def test_exception_handler_manager_registers_lists_and_resolves_mro() -> None:
    manager = ExceptionHandlerManager()

    class DomainError(Exception):
        pass

    class ChildDomainError(DomainError):
        pass

    @manager.exception_handler([DomainError, KeyError])
    def handler(exc: Exception):
        return type(exc).__name__

    assert manager.lookup_exception_handler(ChildDomainError) is handler
    assert manager.lookup_exception_handler(KeyError) is handler
    assert manager.lookup_exception_handler(RuntimeError) is None


def test_exception_handler_manager_bulk_update_copy_and_clear() -> None:
    manager = ExceptionHandlerManager()

    def handler(exc: Exception):
        return str(exc)

    manager.update_exception_handlers({ValueError: handler})
    registered = manager.get_registered_handlers()
    registered.clear()

    assert manager.lookup_exception_handler(ValueError) is handler

    manager.clear_handlers()

    assert manager.lookup_exception_handler(ValueError) is None
