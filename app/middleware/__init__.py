"""
Middleware module.

This module contains middleware components for:
- Rate limiting
- API key authentication
- Request logging
- Exception handling
"""

from app.middleware.rate_limit import RateLimitMiddleware, RateLimiter
from app.middleware.auth import verify_api_key, optional_api_key, api_key_header
from app.middleware.error_handlers import register_exception_handlers
from app.middleware.logging import RequestLoggingMiddleware

__all__ = [
    "RateLimitMiddleware",
    "RateLimiter",
    "verify_api_key",
    "optional_api_key",
    "api_key_header",
    "register_exception_handlers",
    "RequestLoggingMiddleware",
]
