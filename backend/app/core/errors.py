"""Application errors and their HTTP representation.

Every failure the API can produce is modelled as an :class:`AppError` carrying
a stable machine-readable ``code``. Handlers never forward driver internals,
tracebacks or configuration values to the client; details are logged server-side
only.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from pymongo.errors import PyMongoError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

#: Starlette renamed these constants; resolve them defensively so the code works
#: on either side of the rename without emitting a deprecation warning.
HTTP_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
HTTP_413 = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)


class AppError(Exception):
    """Base class for expected, client-visible failures."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        #: Headers the error response must carry. ``RateLimitedError`` uses this
        #: for ``Retry-After``; the value has to travel on the exception because
        #: the handler builds a *new* response and would otherwise discard a
        #: header set on the route's injected ``Response``.
        self.headers: dict[str, str] = dict(headers or {})
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message}}


class BadRequestError(AppError):
    """The request is malformed (e.g. an invalid identifier)."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"
    message = "The request could not be processed."


class NotFoundError(AppError):
    """The requested resource does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppError):
    """The request conflicts with the current state of the resource."""

    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class ServiceUnavailableError(AppError):
    """A backing service (usually the database) is unavailable."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"
    message = "A required service is currently unavailable."


class UnsupportedMediaTypeError(AppError):
    """The uploaded file is not an accepted media type."""

    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_media_type"
    message = "The uploaded file type is not supported."


class PayloadTooLargeError(AppError):
    """The uploaded file exceeds the configured size limit."""

    status_code = HTTP_413
    code = "payload_too_large"
    message = "The uploaded file is too large."


class InvalidMediaError(AppError):
    """The upload is malformed or its declared type contradicts its content."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_media"
    message = "The uploaded file is not valid."


# -- Storage (S3) ------------------------------------------------------------
#
# Storage failures are *upstream* problems, not client mistakes, so they are
# reported as 502/503 rather than 400/422. The messages are fixed strings: a
# botocore message can echo the bucket ARN, the request id and, in some failure
# modes, credential material, none of which belongs in an API response.


class StorageNotConfiguredError(AppError):
    """Storage credentials or the bucket name are missing."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "storage_not_configured"
    message = "Media storage is not configured on this server."


class StorageUnavailableError(AppError):
    """The storage service could not be reached."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "storage_unavailable"
    message = "Media storage is temporarily unavailable."


class StorageAccessDeniedError(AppError):
    """The credentials were rejected, or lack permission for the operation."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "storage_access_denied"
    message = "Media storage rejected the request."


class StorageError(AppError):
    """A storage operation failed."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "storage_error"
    message = "The media storage operation failed."


class StorageObjectNotFoundError(AppError):
    """The referenced object does not exist in the bucket."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "storage_object_not_found"
    message = "The stored file was not found."


#: Stable codes for framework-generated errors, so clients never have to parse
#: two different body shapes.
HTTP_ERROR_CODES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_413_CONTENT_TOO_LARGE: "payload_too_large",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
}

HTTP_ERROR_MESSAGES: dict[int, str] = {
    HTTP_413: "The uploaded file is too large.",
    status.HTTP_404_NOT_FOUND: "The requested resource was not found.",
    status.HTTP_405_METHOD_NOT_ALLOWED: "This method is not allowed for the resource.",
}


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error}, headers=headers or None)


def install_exception_handlers(app: FastAPI) -> None:
    """Register safe handlers for every failure mode."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("Application error [%s]: %s", exc.code, exc.message)
        return _error_response(exc.status_code, exc.code, exc.message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Only the location, message and rule are forwarded. The submitted
        # ``input`` value is deliberately dropped so credentials or personal
        # data can never be echoed back in an error body.
        details = [
            {
                "location": [str(part) for part in error.get("loc", ())],
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return _error_response(
            HTTP_422,
            "validation_error",
            "Request validation failed.",
            details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Give framework errors the same shape as domain errors.

        Without this, an unknown route or wrong method returns Starlette's
        ``{"detail": ...}`` body, so clients would have to parse two different
        error formats. Only the status code and a fixed message are used -
        ``exc.detail`` is not forwarded.
        """
        code = HTTP_ERROR_CODES.get(exc.status_code, "http_error")
        message = HTTP_ERROR_MESSAGES.get(exc.status_code, exc.detail)
        return _error_response(exc.status_code, code, message)

    @app.exception_handler(ValidationError)
    async def _handle_domain_validation_error(_: Request, exc: ValidationError) -> JSONResponse:
        """Catch validation raised below the request-parsing layer.

        Reached when a service revalidates a merged document and finds a
        cross-field rule broken. Field locations and messages are forwarded;
        offending values are not.
        """
        details = [
            {
                "location": [str(part) for part in error.get("loc", ())],
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return _error_response(
            HTTP_422,
            "validation_error",
            "Request validation failed.",
            details,
        )

    @app.exception_handler(PyMongoError)
    async def _handle_database_error(_: Request, exc: PyMongoError) -> JSONResponse:
        # The driver message can contain hosts, index names and topology data,
        # so only the exception type is logged and a generic body is returned.
        logger.error("Database operation failed (%s)", type(exc).__name__, exc_info=True)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "database_error",
            "A database error occurred. Please try again later.",
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error (%s)", type(exc).__name__, exc_info=True)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred.",
        )
