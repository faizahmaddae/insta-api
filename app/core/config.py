"""
Application configuration management using Pydantic Settings.
All configuration is loaded from environment variables or .env file.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        app_name: Name of the application
        app_version: Current API version
        debug: Enable debug mode
        api_prefix: URL prefix for all API routes
        
        # Instagram credentials (optional, for authenticated requests)
        instagram_username: Instagram username for authenticated operations
        instagram_password: Instagram password
        session_file_path: Path to store/load session files
        
        # Rate limiting
        rate_limit_requests: Max requests per window
        rate_limit_window: Time window in seconds
        
        # Download settings
        download_dir: Directory for downloaded media
        max_concurrent_downloads: Maximum concurrent download operations
        
        # Security
        api_key: Optional API key for authentication
        cors_origins: Allowed CORS origins
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_name: str = "Instaloader REST API"
    app_version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = "/api/v1"
    
    # Instagram credentials (optional)
    instagram_username: Optional[str] = None
    instagram_password: Optional[str] = None
    session_file_path: str = "./sessions"
    
    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds
    
    # Download settings
    download_dir: str = "./downloads"
    max_concurrent_downloads: int = 3
    request_timeout: int = 300  # 5 minutes
    
    # Security
    api_key: Optional[str] = None
    cors_origins: str = "*"  # Comma-separated list or "*"
    
    # Caching (Redis for production)
    redis_url: Optional[str] = None  # e.g., "redis://localhost:6379"
    cache_ttl_profile: int = 600     # 10 minutes
    cache_ttl_posts: int = 300       # 5 minutes
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def session_path(self) -> Path:
        """Get session file directory as Path object."""
        path = Path(self.session_file_path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def downloads_path(self) -> Path:
        """Get downloads directory as Path object."""
        path = Path(self.download_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()
