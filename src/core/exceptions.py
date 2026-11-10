from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base class for all business/domain errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR", details: Any = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details


# Backward compatibility alias
DomainException = DomainError


class EntityNotFoundError(DomainError):
    """Raised when an entity is not found or not owned by user."""

    def __init__(self, message: str = "Resource not found", details: Any = None):
        super().__init__(message=message, code="NOT_FOUND", details=details)


EntityNotFoundException = EntityNotFoundError


class UnauthorizedError(DomainError):
    """Raised for authentication failures."""

    def __init__(self, message: str = "Authentication required", details: Any = None):
        super().__init__(message=message, code="UNAUTHORIZED", details=details)


UnauthorizedException = UnauthorizedError


class ForbiddenError(DomainError):
    """Raised when user lacks permission to access resource."""

    def __init__(self, message: str = "Access forbidden", details: Any = None):
        super().__init__(message=message, code="FORBIDDEN", details=details)


ForbiddenException = ForbiddenError


class ConflictError(DomainError):
    """Raised when an operation would violate unique constraints or cause conflicts."""

    def __init__(
        self, message: str = "Resource already exists or conflicts", details: Any = None
    ):
        super().__init__(message=message, code="CONFLICT", details=details)


ConflictException = ConflictError


class BusinessRuleValidationError(DomainError):
    """Raised when input violates financial or business rules."""

    def __init__(self, message: str = "Business rule violation", details: Any = None):
        super().__init__(message=message, code="VALIDATION_ERROR", details=details)


BusinessRuleValidationException = BusinessRuleValidationError


def register_exception_handlers(app: FastAPI) -> None:
    """Registers standard JSON error response handlers for domain and HTTP exceptions."""

    @app.exception_handler(EntityNotFoundError)
    async def entity_not_found_handler(
        request: Request, exc: EntityNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(
        request: Request, exc: UnauthorizedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(BusinessRuleValidationError)
    async def business_validation_handler(
        request: Request, exc: BusinessRuleValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "REQUEST_VALIDATION_ERROR",
                    "message": "Invalid request parameters",
                    "details": exc.errors(),
                }
            },
        )
