"""
Rate limiting middleware using a sliding window algorithm.
Protects the API from abuse and helps avoid Instagram rate limits.
"""

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import get_settings
from app.core.logging import logger


@dataclass
class RateLimitState:
    """Tracks rate limit state for a client."""
    requests: list[float]  # Timestamps of requests
    
    def __init__(self):
        self.requests = []


class RateLimiter:
    """
    Sliding window rate limiter.
    
    Uses a sliding window approach to track requests per client.
    More accurate than fixed windows and prevents burst attacks
    at window boundaries.
    """
    
    def __init__(
        self,
        requests_limit: int,
        window_seconds: int
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_limit: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self._clients: dict[str, RateLimitState] = defaultdict(RateLimitState)
    
    def _get_client_key(self, request: Request) -> str:
        """
        Get unique identifier for the client.
        
        Uses X-Forwarded-For if behind a proxy, otherwise client IP.
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Get first IP in the chain (original client)
            return forwarded.split(",")[0].strip()
        
        return request.client.host if request.client else "unknown"
    
    def _cleanup_old_requests(self, state: RateLimitState, now: float) -> None:
        """Remove requests outside the current window."""
        cutoff = now - self.window_seconds
        state.requests = [ts for ts in state.requests if ts > cutoff]
    
    def is_allowed(self, request: Request) -> tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Tuple of (is_allowed, remaining_requests, reset_seconds)
        """
        client_key = self._get_client_key(request)
        state = self._clients[client_key]
        now = time.time()
        
        # Cleanup old requests
        self._cleanup_old_requests(state, now)
        
        # Check if under limit
        remaining = max(0, self.requests_limit - len(state.requests))
        
        if len(state.requests) >= self.requests_limit:
            # Calculate time until oldest request expires
            oldest = min(state.requests) if state.requests else now
            reset_seconds = int((oldest + self.window_seconds) - now)
            return False, 0, max(1, reset_seconds)
        
        # Record this request
        state.requests.append(now)
        
        return True, remaining - 1, self.window_seconds
    
    def get_headers(self, remaining: int, reset_seconds: int) -> dict[str, str]:
        """Generate rate limit headers for response."""
        return {
            "X-RateLimit-Limit": str(self.requests_limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_seconds),
            "X-RateLimit-Window": str(self.window_seconds)
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    
    Applies rate limiting to all requests and adds rate limit
    headers to responses.
    """
    
    def __init__(self, app, limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        
        if limiter is None:
            settings = get_settings()
            self.limiter = RateLimiter(
                requests_limit=settings.rate_limit_requests,
                window_seconds=settings.rate_limit_window
            )
        else:
            self.limiter = limiter
        
        # Paths that should bypass rate limiting
        self.exempt_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with rate limiting."""
        
        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        
        # Check rate limit
        is_allowed, remaining, reset_seconds = self.limiter.is_allowed(request)
        
        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for {request.client.host if request.client else 'unknown'}"
            )
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {reset_seconds} seconds.",
                headers=self.limiter.get_headers(0, reset_seconds)
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        headers = self.limiter.get_headers(remaining, reset_seconds)
        for key, value in headers.items():
            response.headers[key] = value
        
        return response
