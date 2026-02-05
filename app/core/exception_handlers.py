"""
Global exception handlers for FastAPI application.
Provides consistent error response format across all endpoints.
"""

import logging
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException, ErrorCode

logger = logging.getLogger(__name__)


def generate_request_id() -> str:
    """Generate a unique request ID for error tracing"""
    return str(uuid.uuid4())[:8]


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handle custom AppException and its subclasses.
    Returns a structured error response with error code.
    """
    request_id = generate_request_id()

    # Log the error
    logger.warning(
        "AppException: %s (code=%s, status=%d, request_id=%s, path=%s)",
        exc.message,
        exc.code.value,
        exc.status_code,
        request_id,
        request.url.path,
    )

    response_body = exc.to_dict()

    return JSONResponse(
        status_code=exc.status_code,
        content=response_body,
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    Returns errors in the standard format with field locations.
    """
    request_id = generate_request_id()

    # Log validation errors
    logger.warning(
        "ValidationError: %s (request_id=%s, path=%s)",
        exc.errors(),
        request_id,
        request.url.path,
    )

    # Format validation errors
    errors = []
    for error in exc.errors():
        errors.append({
            "loc": list(error["loc"]),
            "msg": error["msg"],
            "type": error["type"],
        })

    response_body: dict[str, Any] = {
        "detail": errors,
        "code": ErrorCode.VALIDATION_ERROR.value,
    }

    return JSONResponse(
        status_code=422,
        content=response_body,
        headers={"X-Request-ID": request_id},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle standard HTTP exceptions from FastAPI/Starlette.
    Converts them to our standardized response format.
    """
    request_id = generate_request_id()

    # Map status codes to error codes
    status_to_code = {
        400: ErrorCode.VALIDATION_ERROR,
        401: ErrorCode.AUTH_NOT_AUTHENTICATED,
        403: ErrorCode.AUTHZ_FORBIDDEN,
        404: ErrorCode.RESOURCE_NOT_FOUND,
        409: ErrorCode.RESOURCE_CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        500: ErrorCode.SERVER_ERROR,
        502: ErrorCode.SERVER_UNAVAILABLE,
        503: ErrorCode.SERVER_UNAVAILABLE,
    }

    error_code = status_to_code.get(exc.status_code, ErrorCode.SERVER_ERROR)

    logger.warning(
        "HTTPException: %s (status=%d, request_id=%s, path=%s)",
        exc.detail,
        exc.status_code,
        request_id,
        request.url.path,
    )

    response_body: dict[str, Any] = {
        "detail": exc.detail or "An error occurred",
        "code": error_code.value,
    }

    return JSONResponse(
        status_code=exc.status_code,
        content=response_body,
        headers={"X-Request-ID": request_id},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions.
    Logs the full error for debugging and returns a generic error response.
    """
    request_id = generate_request_id()

    # Log the full exception with traceback
    logger.exception(
        "Unhandled exception (request_id=%s, path=%s): %s",
        request_id,
        request.url.path,
        str(exc),
    )

    response_body: dict[str, Any] = {
        "detail": "Server xatoligi yuz berdi. Keyinroq urinib ko'ring.",
        "code": ErrorCode.SERVER_ERROR.value,
    }

    return JSONResponse(
        status_code=500,
        content=response_body,
        headers={"X-Request-ID": request_id},
    )
