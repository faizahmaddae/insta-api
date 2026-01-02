"""
Exception handlers for the API.
Maps exceptions to proper HTTP responses.
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import APIException
from app.core.logging import logger
from app.models.common import ErrorResponse


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """
    Handle custom API exceptions.
    
    Converts APIException to a standardized JSON response.
    """
    logger.error(f"API Exception: {exc.error_code} - {exc.message}")
    
    error_response = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(mode="json")
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle HTTP exceptions.
    
    Standardizes HTTP exceptions to our response format.
    """
    error_response = ErrorResponse(
        error_code=f"HTTP_{exc.status_code}",
        message=exc.detail or "An error occurred",
        details=None
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(mode="json"),
        headers=getattr(exc, "headers", None)
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    
    Provides detailed error information about validation failures.
    """
    # Extract validation errors
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    error_response = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details=errors
    )
    
    return JSONResponse(
        status_code=422,
        content=error_response.model_dump(mode="json")
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.
    
    Catches all unhandled exceptions and returns a generic error response.
    Logs the full exception for debugging.
    """
    logger.exception(f"Unhandled exception: {exc}")
    
    error_response = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message="An internal error occurred",
        details=str(exc) if request.app.debug else None
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump(mode="json")
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
