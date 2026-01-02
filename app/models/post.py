"""
Pydantic models for Post-related requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class PostType(str, Enum):
    """Types of Instagram posts."""
    IMAGE = "GraphImage"
    VIDEO = "GraphVideo"
    SIDECAR = "GraphSidecar"


class MediaItem(BaseModel):
    """Single media item (for sidecar posts)."""
    
    is_video: bool = Field(..., description="Whether this item is a video")
    display_url: str = Field(..., description="URL of the image/thumbnail")
    video_url: Optional[str] = Field(None, description="URL of the video (if is_video)")


class LocationInfo(BaseModel):
    """Post location information."""
    
    id: int = Field(..., description="Location ID")
    name: str = Field(..., description="Location name")
    slug: str = Field(..., description="URL-friendly location name")
    lat: Optional[float] = Field(None, description="Latitude")
    lng: Optional[float] = Field(None, description="Longitude")


class CommentInfo(BaseModel):
    """Comment information."""
    
    id: int = Field(..., description="Comment ID")
    text: str = Field(..., description="Comment text")
    owner_username: str = Field(..., description="Comment author username")
    owner_id: int = Field(..., description="Comment author ID")
    created_at: datetime = Field(..., description="Comment creation time (UTC)")
    likes_count: int = Field(0, description="Number of likes on comment")


class PostBase(BaseModel):
    """Base post information."""
    
    shortcode: str = Field(..., description="Post shortcode (used in URL)")
    media_id: int = Field(..., description="Post media ID")
    typename: PostType = Field(..., description="Type of post")
    owner_username: str = Field(..., description="Post owner's username")
    owner_id: int = Field(..., description="Post owner's ID")


class PostResponse(PostBase):
    """Full post response with all details."""
    
    caption: Optional[str] = Field(None, description="Post caption")
    caption_hashtags: list[str] = Field([], description="Hashtags in caption")
    caption_mentions: list[str] = Field([], description="Mentioned users in caption")
    tagged_users: list[str] = Field([], description="Tagged users in the post")
    
    # Media URLs
    display_url: str = Field(..., description="Main display image/thumbnail URL")
    video_url: Optional[str] = Field(None, description="Video URL (if video post)")
    
    # For sidecar posts
    sidecar_items: list[MediaItem] = Field([], description="Media items in sidecar")
    media_count: int = Field(1, description="Number of media items")
    
    # Engagement metrics
    likes: int = Field(0, description="Number of likes")
    comments_count: int = Field(0, description="Number of comments")
    video_view_count: Optional[int] = Field(None, description="Video views (if video)")
    video_duration: Optional[float] = Field(None, description="Video duration in seconds")
    
    # Timestamps
    date_utc: datetime = Field(..., description="Post creation time (UTC)")
    
    # Location
    location: Optional[LocationInfo] = Field(None, description="Post location")
    
    # Status
    is_video: bool = Field(..., description="Whether post contains video")
    is_sponsored: bool = Field(False, description="Whether post is sponsored")
    
    # Viewer interaction (if logged in)
    viewer_has_liked: Optional[bool] = Field(None, description="Whether viewer liked this post")
    
    class Config:
        json_schema_extra = {
            "example": {
                "shortcode": "ABC123xyz",
                "media_id": 1234567890123456789,
                "typename": "GraphImage",
                "owner_username": "instagram",
                "owner_id": 25025320,
                "caption": "Welcome to Instagram! 🎉",
                "caption_hashtags": ["instagram", "welcome"],
                "caption_mentions": ["meta"],
                "tagged_users": ["user1", "user2"],
                "display_url": "https://instagram.com/...",
                "video_url": None,
                "sidecar_items": [],
                "media_count": 1,
                "likes": 1000000,
                "comments_count": 50000,
                "video_view_count": None,
                "video_duration": None,
                "date_utc": "2024-01-15T12:00:00Z",
                "location": None,
                "is_video": False,
                "is_sponsored": False,
                "viewer_has_liked": None
            }
        }


class PostRequest(BaseModel):
    """Request model for post lookup by shortcode."""
    
    shortcode: str = Field(..., min_length=1, description="Post shortcode")
    
    class Config:
        json_schema_extra = {
            "example": {
                "shortcode": "ABC123xyz"
            }
        }


class PostsListRequest(BaseModel):
    """Request model for fetching multiple posts."""
    
    username: str = Field(..., min_length=1, max_length=30, description="Instagram username")
    limit: int = Field(12, ge=1, le=50, description="Maximum number of posts to return")
    include_captions: bool = Field(True, description="Include post captions")
    include_location: bool = Field(False, description="Include location data")


class PostsListResponse(BaseModel):
    """Response for list of posts."""
    
    posts: list[PostResponse] = Field(..., description="List of posts")
    count: int = Field(..., description="Number of posts returned")
    has_more: bool = Field(False, description="Whether more posts are available")
    profile_username: str = Field(..., description="Profile username")


class HashtagPostsRequest(BaseModel):
    """Request for posts by hashtag."""
    
    hashtag: str = Field(..., min_length=1, max_length=100, description="Hashtag (without #)")
    limit: int = Field(12, ge=1, le=50, description="Maximum number of posts")
    top_posts_only: bool = Field(False, description="Only return top posts")


class HashtagInfo(BaseModel):
    """Hashtag information."""
    
    name: str = Field(..., description="Hashtag name (without #)")
    hashtag_id: int = Field(..., description="Hashtag ID")
    media_count: int = Field(..., description="Number of posts with this hashtag")
    profile_pic_url: str = Field(..., description="Hashtag cover image URL")
    description: Optional[str] = Field(None, description="Hashtag description")
    is_following: Optional[bool] = Field(None, description="Whether user follows this hashtag")


class CommentsResponse(BaseModel):
    """Response for post comments."""
    
    comments: list[CommentInfo] = Field(..., description="List of comments")
    count: int = Field(..., description="Number of comments returned")
    total_count: int = Field(..., description="Total comments on post")


class LikesResponse(BaseModel):
    """Response for post likes."""
    
    users: list[dict[str, Any]] = Field(..., description="List of users who liked")
    count: int = Field(..., description="Number of likes returned")
