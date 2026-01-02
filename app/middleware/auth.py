"""
API Key authentication middleware.
Optional security layer for protecting the API.
"""

from typing import Optional

from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.config import get_settings
from app.core.logging import logger

# API Key header definition
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header)
) -> bool:
    """
    Verify API key if configured.
    
    This is a FastAPI dependency that can be added to routes
    to require API key authentication.
    
    Args:
        api_key: API key from X-API-Key header
        
    Returns:
        True if API key is valid or not configured
        
    Raises:
        HTTPException: If API key is required but invalid
    """
    settings = get_settings()
    
    # If no API key is configured, allow all requests
    if not settings.api_key:
        return True
    
    # Check if API key matches
    if api_key == settings.api_key:
        return True
    
    # Log failed attempt
    logger.warning(f"Invalid API key attempt")
    
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "ApiKey"}
    )


async def optional_api_key(
    api_key: Optional[str] = Security(api_key_header)
) -> Optional[str]:
    """
    Optional API key verification.
    
    Returns the API key if provided and valid, None otherwise.
    Does not raise an exception if no key is provided.
    """
    settings = get_settings()
    
    if not settings.api_key:
        return None
    
    if api_key == settings.api_key:
        return api_key
    
    return None
