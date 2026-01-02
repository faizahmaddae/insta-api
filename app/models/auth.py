"""
Pydantic models for authentication-related requests and responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request model for Instagram login."""
    
    username: str = Field(..., min_length=1, max_length=30, description="Instagram username")
    password: str = Field(..., min_length=1, description="Instagram password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "your_username",
                "password": "your_password"
            }
        }


class TwoFactorRequest(BaseModel):
    """Request model for two-factor authentication."""
    
    username: str = Field(..., min_length=1, max_length=30, description="Instagram username")
    code: str = Field(..., min_length=6, max_length=6, description="2FA code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "your_username",
                "code": "123456"
            }
        }


class SessionLoadRequest(BaseModel):
    """Request model for loading a saved session."""
    
    username: str = Field(..., min_length=1, max_length=30, description="Instagram username")
    session_file: Optional[str] = Field(None, description="Custom session file path")


class LoginResponse(BaseModel):
    """Response model for successful login."""
    
    success: bool = Field(..., description="Whether login was successful")
    username: str = Field(..., description="Logged in username")
    message: str = Field(..., description="Status message")
    requires_2fa: bool = Field(False, description="Whether 2FA is required")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "username": "your_username",
                "message": "Successfully logged in",
                "requires_2fa": False
            }
        }


class SessionStatusResponse(BaseModel):
    """Response model for session status check."""
    
    is_logged_in: bool = Field(..., description="Whether user is logged in")
    username: Optional[str] = Field(None, description="Logged in username (if any)")
    session_valid: bool = Field(False, description="Whether session is valid")
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_logged_in": True,
                "username": "your_username",
                "session_valid": True
            }
        }


class LogoutResponse(BaseModel):
    """Response model for logout."""
    
    success: bool = Field(..., description="Whether logout was successful")
    message: str = Field(..., description="Status message")
