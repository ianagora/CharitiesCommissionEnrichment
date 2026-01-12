"""User-related Pydantic schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    organization: Optional[str] = Field(None, max_length=255)
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password complexity."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        # Require special character
        special_chars = "!@#$%^&*()_+-=[]{}|;:',.<>?/`~"
        if not any(c in special_chars for c in v):
            raise ValueError("Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:',.<>?/`~)")
        return v


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    full_name: Optional[str] = Field(None, max_length=255)
    organization: Optional[str] = Field(None, max_length=255)


class UserResponse(BaseModel):
    """Schema for user response."""
    id: UUID
    email: EmailStr
    full_name: Optional[str]
    organization: Optional[str]
    is_active: bool
    is_verified: bool
    api_key: Optional[str]
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema for JWT tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Schema for decoded token data."""
    user_id: Optional[UUID] = None
    email: Optional[str] = None
    is_superuser: bool = False
    token_version: Optional[int] = None
    token_family: Optional[str] = None


class PasswordChange(BaseModel):
    """Schema for changing password."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password complexity."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        # Require special character
        special_chars = "!@#$%^&*()_+-=[]{}|;:',.<>?/`~"
        if not any(c in special_chars for c in v):
            raise ValueError("Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:',.<>?/`~)")
        return v
