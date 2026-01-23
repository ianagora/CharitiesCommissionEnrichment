"""User-related Pydantic schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# Password complexity requirements
PASSWORD_SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:',.<>?/`~"


def validate_password_complexity(password: str) -> str:
    """
    Validate password meets complexity requirements.
    
    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")
    if not any(c in PASSWORD_SPECIAL_CHARS for c in password):
        raise ValueError(f"Password must contain at least one special character ({PASSWORD_SPECIAL_CHARS})")
    return password


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
        return validate_password_complexity(v)


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    full_name: Optional[str] = Field(None, max_length=255)
    organization: Optional[str] = Field(None, max_length=255)


class UserResponse(BaseModel):
    """Schema for user response - excludes sensitive data."""
    id: UUID
    email: EmailStr
    full_name: Optional[str]
    organization: Optional[str]
    is_active: bool
    is_superuser: bool = False
    is_verified: bool
    has_api_key: bool = False  # Only indicate if API key exists, don't expose it
    two_factor_enabled: bool = False
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_user(cls, user) -> "UserResponse":
        """Create response from User model with computed fields."""
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            organization=user.organization,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            is_verified=user.is_verified,
            has_api_key=user.api_key_hash is not None,
            two_factor_enabled=user.two_factor_enabled,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str
    totp_code: Optional[str] = None  # 6-digit TOTP code or backup code


class Token(BaseModel):
    """Schema for JWT tokens (access token only - refresh token in httpOnly cookie)."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenWithRefresh(BaseModel):
    """Schema for JWT tokens including refresh token (for backwards compatibility)."""
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
    token_jti: Optional[str] = None  # Unique token ID for refresh token validation


class PasswordChange(BaseModel):
    """Schema for changing password."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password complexity."""
        return validate_password_complexity(v)
