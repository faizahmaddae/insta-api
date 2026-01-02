"""
Pydantic models for Profile-related requests and responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProfileBase(BaseModel):
    """Base profile information."""
    
    username: str = Field(..., description="Instagram username")
    user_id: int = Field(..., description="Instagram user ID")
    full_name: str = Field(..., description="Full name")
    biography: str = Field("", description="Profile biography")
    is_private: bool = Field(..., description="Whether profile is private")
    is_verified: bool = Field(..., description="Whether profile is verified")
    is_business: bool = Field(False, description="Whether it's a business account")


class ProfileResponse(ProfileBase):
    """Full profile response with statistics."""
    
    followers: int = Field(..., description="Number of followers")
    followees: int = Field(..., description="Number of accounts followed")
    media_count: int = Field(..., description="Total number of posts")
    igtv_count: int = Field(0, description="Number of IGTV posts")
    profile_pic_url: str = Field(..., description="Profile picture URL")
    external_url: Optional[str] = Field(None, description="External URL in bio")
    business_category: Optional[str] = Field(None, description="Business category name")
    
    # Viewer relationship (if logged in)
    followed_by_viewer: Optional[bool] = Field(None, description="Whether viewer follows this profile")
    follows_viewer: Optional[bool] = Field(None, description="Whether this profile follows viewer")
    blocked_by_viewer: Optional[bool] = Field(None, description="Whether viewer blocked this profile")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "instagram",
                "user_id": 25025320,
                "full_name": "Instagram",
                "biography": "Bringing you closer to the people and things you love.",
                "is_private": False,
                "is_verified": True,
                "is_business": True,
                "followers": 500000000,
                "followees": 100,
                "media_count": 7000,
                "igtv_count": 50,
                "profile_pic_url": "https://instagram.com/...",
                "external_url": "https://about.instagram.com",
                "business_category": "Internet Company"
            }
        }


class ProfileRequest(BaseModel):
    """Request model for profile lookup."""
    
    username: str = Field(..., min_length=1, max_length=30, description="Instagram username")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "instagram"
            }
        }


class ProfileIdRequest(BaseModel):
    """Request model for profile lookup by ID."""
    
    user_id: int = Field(..., gt=0, description="Instagram user ID")


class FollowerResponse(BaseModel):
    """Response for followers/followees list."""
    
    users: list[ProfileBase] = Field(..., description="List of profiles")
    count: int = Field(..., description="Total count")
    has_more: bool = Field(False, description="Whether more results are available")
    
    class Config:
        json_schema_extra = {
            "example": {
                "users": [
                    {
                        "username": "user1",
                        "user_id": 123456,
                        "full_name": "User One",
                        "biography": "Hello world",
                        "is_private": False,
                        "is_verified": False,
                        "is_business": False
                    }
                ],
                "count": 1,
                "has_more": True
            }
        }


class SimilarAccountsRequest(BaseModel):
    """Request for similar accounts lookup."""
    
    username: str = Field(..., min_length=1, max_length=30, description="Instagram username")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")
