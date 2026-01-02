"""
Request logging middleware.
Logs all incoming requests and outgoing responses.
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.
    
    Logs:
    - Request method, path, and client info
    - Response status code and processing time
    - Assigns a unique request ID for tracing
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        
        # Add request ID to state for use in other parts of the app
        request.state.request_id = request_id
        
        # Log incoming request
        client_ip = request.client.host if request.client else "unknown"
        logger.info(
            f"[{request_id}] --> {request.method} {request.url.path} "
            f"from {client_ip}"
        )
        
        # Time the request
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Log response
            logger.info(
                f"[{request_id}] <-- {response.status_code} "
                f"({process_time:.2f}ms)"
            )
            
            # Add request ID and timing headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
            
            return response
            
        except Exception as e:
            # Log error
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"[{request_id}] <-- ERROR {type(e).__name__}: {e} "
                f"({process_time:.2f}ms)"
            )
            raise
