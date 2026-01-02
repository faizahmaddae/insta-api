"""
Common response models used across the API.
"""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    success: bool = Field(False, description="Always false for errors")
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Any] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "PROFILE_NOT_FOUND",
                "message": "Profile 'nonexistent_user' not found",
                "details": {"username": "nonexistent_user"},
                "timestamp": "2024-01-15T12:00:00Z"
            }
        }


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response wrapper."""
    
    success: bool = Field(True, description="Always true for success")
    data: T = Field(..., description="Response data")
    message: Optional[str] = Field(None, description="Optional status message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {},
                "message": "Operation completed successfully"
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    
    success: bool = Field(True, description="Operation success status")
    data: list[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items available")
    page: int = Field(1, description="Current page number")
    per_page: int = Field(..., description="Items per page")
    has_more: bool = Field(..., description="Whether more items are available")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": [],
                "total": 100,
                "page": 1,
                "per_page": 20,
                "has_more": True
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Current timestamp")
    instagram_session_active: bool = Field(..., description="Whether an Instagram session is active")
    logged_in_user: Optional[str] = Field(None, description="Username of logged-in user if any")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2024-01-15T12:00:00Z",
                "instagram_session_active": True,
                "logged_in_user": "my_username"
            }
        }


class DownloadRequest(BaseModel):
    """Request model for download operations."""
    
    target: str = Field(..., description="Target to download (username, shortcode, etc.)")
    download_type: str = Field(..., description="Type of download: profile, post, story, highlight")
    options: Optional[dict[str, Any]] = Field(None, description="Additional download options")
    
    class Config:
        json_schema_extra = {
            "example": {
                "target": "instagram",
                "download_type": "profile",
                "options": {
                    "include_stories": True,
                    "include_highlights": False,
                    "max_posts": 10
                }
            }
        }


class DownloadResponse(BaseModel):
    """Response model for download operations."""
    
    success: bool = Field(..., description="Whether download was successful")
    download_id: str = Field(..., description="Unique download operation ID")
    target: str = Field(..., description="Download target")
    files_downloaded: int = Field(0, description="Number of files downloaded")
    download_path: str = Field(..., description="Path where files were saved")
    message: str = Field(..., description="Status message")


class SearchRequest(BaseModel):
    """Request model for search operations."""
    
    query: str = Field(..., min_length=1, max_length=100, description="Search query")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")


class SearchResult(BaseModel):
    """Single search result item."""
    
    type: str = Field(..., description="Result type: profile, hashtag, location")
    name: str = Field(..., description="Result name/username")
    id: int = Field(..., description="Result ID")
    profile_pic_url: Optional[str] = Field(None, description="Profile picture URL")
    description: Optional[str] = Field(None, description="Bio/description")


class SearchResponse(BaseModel):
    """Response model for search operations."""
    
    query: str = Field(..., description="Original search query")
    profiles: list[SearchResult] = Field([], description="Profile results")
    hashtags: list[SearchResult] = Field([], description="Hashtag results")
    locations: list[SearchResult] = Field([], description="Location results")
    total_results: int = Field(0, description="Total number of results")
