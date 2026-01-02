"""
Pydantic models for Story-related requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class StoryItemType(str, Enum):
    """Types of story items."""
    IMAGE = "GraphStoryImage"
    VIDEO = "GraphStoryVideo"


class StoryItemResponse(BaseModel):
    """Single story item response."""
    
    media_id: int = Field(..., description="Story item media ID")
    shortcode: str = Field(..., description="Story item shortcode")
    typename: StoryItemType = Field(..., description="Type of story item")
    
    # Owner info
    owner_username: str = Field(..., description="Story owner's username")
    owner_id: int = Field(..., description="Story owner's ID")
    
    # Media URLs
    display_url: str = Field(..., description="Image/thumbnail URL")
    video_url: Optional[str] = Field(None, description="Video URL (if video)")
    
    # Content
    caption: Optional[str] = Field(None, description="Story caption")
    caption_hashtags: list[str] = Field([], description="Hashtags in caption")
    caption_mentions: list[str] = Field([], description="Mentioned users")
    
    # Timestamps
    date_utc: datetime = Field(..., description="Creation time (UTC)")
    expiring_utc: datetime = Field(..., description="Expiration time (UTC)")
    
    # Status
    is_video: bool = Field(..., description="Whether item is a video")
    
    class Config:
        json_schema_extra = {
            "example": {
                "media_id": 1234567890123456789,
                "shortcode": "ABC123",
                "typename": "GraphStoryImage",
                "owner_username": "instagram",
                "owner_id": 25025320,
                "display_url": "https://instagram.com/...",
                "video_url": None,
                "caption": "Hello! 👋",
                "caption_hashtags": [],
                "caption_mentions": [],
                "date_utc": "2024-01-15T12:00:00Z",
                "expiring_utc": "2024-01-16T12:00:00Z",
                "is_video": False
            }
        }


class StoryResponse(BaseModel):
    """Story collection response for a user."""
    
    owner_username: str = Field(..., description="Story owner's username")
    owner_id: int = Field(..., description="Story owner's ID")
    item_count: int = Field(..., description="Number of items in story")
    items: list[StoryItemResponse] = Field(..., description="Story items")
    latest_media_utc: datetime = Field(..., description="Most recent item timestamp")
    last_seen_utc: Optional[datetime] = Field(None, description="Last seen timestamp")


class StoriesRequest(BaseModel):
    """Request for fetching stories."""
    
    usernames: list[str] = Field(
        default=[],
        max_length=20,
        description="List of usernames to fetch stories for (empty for all followed)"
    )


class StoriesResponse(BaseModel):
    """Response containing multiple users' stories."""
    
    stories: list[StoryResponse] = Field(..., description="List of story collections")
    count: int = Field(..., description="Number of story collections")


class HighlightResponse(BaseModel):
    """Highlight collection response."""
    
    highlight_id: int = Field(..., description="Highlight unique ID")
    title: str = Field(..., description="Highlight title")
    owner_username: str = Field(..., description="Highlight owner's username")
    owner_id: int = Field(..., description="Highlight owner's ID")
    item_count: int = Field(..., description="Number of items in highlight")
    cover_url: str = Field(..., description="Cover image URL")
    cover_cropped_url: str = Field(..., description="Cropped cover image URL")
    items: list[StoryItemResponse] = Field([], description="Highlight items (if requested)")


class HighlightsRequest(BaseModel):
    """Request for fetching highlights."""
    
    username: str = Field(..., min_length=1, max_length=30, description="Username to fetch highlights for")
    include_items: bool = Field(False, description="Include items in each highlight")


class HighlightsResponse(BaseModel):
    """Response containing user's highlights."""
    
    username: str = Field(..., description="Profile username")
    highlights: list[HighlightResponse] = Field(..., description="List of highlights")
    count: int = Field(..., description="Number of highlights")
