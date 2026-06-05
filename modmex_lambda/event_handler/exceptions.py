"""Framework exceptions with API Gateway friendly defaults."""
from collections.abc import Sequence
from http import HTTPStatus
from typing import Any
from modmex import ValidationError


class ValidationException(Exception):
    """
    Base exception for all validation errors
    """

    def __init__(self, errors: Sequence[Any]) -> None:
        self._errors = errors

    def errors(self) -> Sequence[Any]:
        return self._errors

class ServiceError(Exception):
    """HTTP Service Error"""

    def __init__(self, status_code: int, msg: str | dict):
        """
        Parameters
        ----------
        status_code: int
            HTTP status code
        msg: str | dict
            Error message. Can be a string or a dictionary
        """
        self.status_code = status_code
        self.msg = msg


class RequestValidationError(ValidationException):
    """Raised when request validation fails."""



class NotFoundError(ServiceError):
    """Raised when no route matches a request path."""
    
    def __init__(self, msg: str | dict = "Not Found"):
        super().__init__(HTTPStatus.NOT_FOUND, msg)


class MethodNotAllowedError(ServiceError):
    """Raised when a path exists but the HTTP method is not allowed."""
    
    def __init__(self, msg: str | dict = "Method Not Allowed"):
        super().__init__(HTTPStatus.METHOD_NOT_ALLOWED, msg)


class BadRequestError(ServiceError):
    """Raised when an incoming event cannot be normalized."""
    
    def __init__(self, msg: str | dict = "Bad Request"):
        super().__init__(HTTPStatus.BAD_REQUEST, msg)


class UnauthorizedError(ServiceError):
    """Raised when a request is not authenticated."""
    
    def __init__(self, msg: str | dict = "Unauthorized"):
        super().__init__(HTTPStatus.UNAUTHORIZED, msg)


class ForbiddenError(ServiceError):
    """Raised when a request is authenticated but not authorized."""
    
    def __init__(self, msg: str | dict = "Forbidden"):
        super().__init__(HTTPStatus.FORBIDDEN, msg)
