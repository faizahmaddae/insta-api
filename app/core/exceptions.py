"""
Custom exceptions for the Instaloader API.
Maps Instaloader exceptions to appropriate HTTP responses.
"""

from typing import Any, Optional


class APIException(Exception):
    """Base exception for all API errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Any] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        super().__init__(self.message)


class AuthenticationError(APIException):
    """Raised when Instagram authentication fails."""
    
    def __init__(self, message: str = "Authentication failed", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            details=details
        )


class ProfileNotFoundError(APIException):
    """Raised when an Instagram profile is not found."""
    
    def __init__(self, username: str):
        super().__init__(
            message=f"Profile '{username}' not found",
            status_code=404,
            error_code="PROFILE_NOT_FOUND",
            details={"username": username}
        )


class PrivateProfileError(APIException):
    """Raised when trying to access a private profile without following."""
    
    def __init__(self, username: str):
        super().__init__(
            message=f"Profile '{username}' is private and not followed",
            status_code=403,
            error_code="PRIVATE_PROFILE",
            details={"username": username}
        )


class PostNotFoundError(APIException):
    """Raised when a post is not found."""
    
    def __init__(self, shortcode: str):
        super().__init__(
            message=f"Post with shortcode '{shortcode}' not found",
            status_code=404,
            error_code="POST_NOT_FOUND",
            details={"shortcode": shortcode}
        )


class RateLimitError(APIException):
    """Raised when Instagram rate limit is hit."""
    
    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED"
        )


class LoginRequiredError(APIException):
    """Raised when an operation requires login."""
    
    def __init__(self, operation: str = "this operation"):
        super().__init__(
            message=f"Login required for {operation}",
            status_code=401,
            error_code="LOGIN_REQUIRED",
            details={"operation": operation}
        )


class InvalidCredentialsError(APIException):
    """Raised when Instagram credentials are invalid."""
    
    def __init__(self):
        super().__init__(
            message="Invalid Instagram credentials",
            status_code=401,
            error_code="INVALID_CREDENTIALS"
        )


class TwoFactorRequiredError(APIException):
    """Raised when 2FA is required for login."""
    
    def __init__(self):
        super().__init__(
            message="Two-factor authentication required",
            status_code=401,
            error_code="TWO_FACTOR_REQUIRED"
        )


class DownloadError(APIException):
    """Raised when a download operation fails."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="DOWNLOAD_ERROR",
            details=details
        )


class ValidationError(APIException):
    """Raised when request validation fails."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details=details
        )


class ServiceUnavailableError(APIException):
    """Raised when the service is temporarily unavailable."""
    
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(
            message=message,
            status_code=503,
            error_code="SERVICE_UNAVAILABLE"
        )
