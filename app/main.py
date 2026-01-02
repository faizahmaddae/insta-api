"""
Instagram Media Extractor API

A simple API to extract media URLs from Instagram posts, reels, profiles, and stories.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging, logger
from app.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    register_exception_handlers,
)
from app.routes.extract import router as extract_router
from app.routes.accounts import router as accounts_router
from app.services.instaloader_service import InstaloaderService
from app.core.accounts import get_account_manager
from app.models.common import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler."""
    logger.info("Starting Instagram API...")
    
    settings = get_settings()
    
    # Initialize service
    service = InstaloaderService()
    
    # Load accounts from file
    account_manager = get_account_manager()
    account_manager.load_from_file("accounts.json")
    account_manager.load_from_env()
    
    # Auto-login if credentials configured
    if settings.instagram_username and settings.instagram_password:
        try:
            await service.login(
                settings.instagram_username,
                settings.instagram_password
            )
            logger.info(f"Auto-logged in as {settings.instagram_username}")
        except Exception as e:
            logger.warning(f"Auto-login failed: {e}")
    
    logger.info("Instagram API started successfully!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Instagram API...")
    try:
        service.close()
    except Exception as e:
        logger.warning(f"Error during shutdown: {e}")
    logger.info("Shutdown complete.")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    setup_logging()
    
    app = FastAPI(
        title="Instagram Media Extractor",
        description="""
# Instagram Media Extractor API

Extract media URLs from Instagram posts, reels, profiles, and stories.

## Main Endpoint

`GET /api?url=<instagram_url>`

### Supported URLs:
- **Posts**: `https://instagram.com/p/SHORTCODE`
- **Reels**: `https://instagram.com/reel/SHORTCODE`
- **Profiles**: `https://instagram.com/USERNAME`
- **Stories**: `https://instagram.com/stories/USERNAME/STORY_ID`

### Response Format:
```json
{
  "status": "success",
  "message": "Success",
  "data": [
    {
      "url": "https://...",
      "thumbnail": "https://...",
      "is_video": false
    }
  ]
}
```
        """,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    
    # Exception handlers
    register_exception_handlers(app)
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-Request-ID",
            "X-Process-Time",
        ],
    )
    
    # Middleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    
    # ==================== Routes ====================
    
    # Main API endpoint - extract media from any Instagram URL
    app.include_router(extract_router, prefix="/api", tags=["Extract"])
    
    # Account management (for testing/managing multi-account pool)
    app.include_router(accounts_router, prefix="/accounts", tags=["Accounts"])
    
    # ==================== System Endpoints ====================
    
    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check() -> HealthResponse:
        """Health check endpoint."""
        service = InstaloaderService()
        account_manager = get_account_manager()
        
        return HealthResponse(
            status="healthy",
            version=settings.app_version,
            instagram_session_active=service.is_logged_in,
            logged_in_user=service._logged_in_user
        )
    
    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint with API info."""
        return {
            "name": "Instagram Media Extractor",
            "version": settings.app_version,
            "usage": "GET /api?url=<instagram_url>",
            "docs": "/docs" if settings.debug else "Docs disabled in production",
            "supported_urls": [
                "https://instagram.com/p/SHORTCODE",
                "https://instagram.com/reel/SHORTCODE",
                "https://instagram.com/USERNAME",
                "https://instagram.com/stories/USERNAME/STORY_ID"
            ]
        }
    
    @app.get("/cache/stats", tags=["System"])
    async def cache_stats():
        """Cache statistics."""
        from app.core.cache import get_cache, InMemoryCache
        cache = get_cache()
        
        if isinstance(cache, InMemoryCache):
            stats = await cache.stats()
            return {"backend": "in-memory", **stats}
        return {"backend": "redis"}
    
    return app


# Create app instance
app = create_application()
