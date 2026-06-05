from __future__ import annotations

from typing import Mapping, Any
from collections.abc import Callable


class ExceptionHandlerManager:

    def __init__(self):
        """Initialize an empty dictionary to store exception handlers."""
        self._exception_handlers: dict[type[Exception], Callable] = {}

    def exception_handler(self, exc_class: type[Exception] | list[type[Exception]]):
        """
        A decorator function that registers a handler for one or more exception types.
        """
        classes = exc_class if isinstance(exc_class, list) else [exc_class]
        
        def register_exception_handler(func: Callable)-> Callable[[Exception], Any]:
            for cls in classes:
                self._exception_handlers[cls] = func
            return func

        return register_exception_handler

    def lookup_exception_handler(self, exp_type: type) -> Callable | None:
        for cls in exp_type.__mro__:
            if cls in self._exception_handlers:
                return self._exception_handlers[cls]
        return None

    def update_exception_handlers(self, handlers: Mapping[type[Exception], Callable]) -> None:
        """
        Updates the exception handlers dictionary with new handler mappings.
        This method allows bulk updates of exception handlers by providing a dictionary
        mapping exception types to handler functions.
        Parameters
        ----------
        handlers : Mapping[Type[Exception], Callable]
            A dictionary mapping exception types to handler functions.
        Example
        -------
        >>> def handle_value_error(e):
        ...     print(f"Value error: {e}")
        ...
        >>> def handle_key_error(e):
        ...     print(f"Key error: {e}")
        ...
        >>> handler_manager.update_exception_handlers({
        ...     ValueError: handle_value_error,
        ...     KeyError: handle_key_error
        ... })
        """
        self._exception_handlers.update(handlers)

    def get_registered_handlers(self) -> dict[type[Exception], Callable]:
        """
        Returns all registered exception handlers.
        Returns
        -------
        Dict[Type[Exception], Callable]
            A dictionary mapping exception types to their handler functions.
        """
        return self._exception_handlers.copy()

    def clear_handlers(self) -> None:
        """
        Clears all registered exception handlers.
        """
        self._exception_handlers.clear()
