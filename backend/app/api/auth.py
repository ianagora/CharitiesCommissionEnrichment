"""Authentication API routes."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.audit import AuditLog, AuditAction
from app.schemas.user import (
    UserCreate, UserResponse, UserLogin, UserUpdate,
    Token, PasswordChange
)
from app.services.auth import AuthService
from app.api.deps import get_current_active_user
from app.config import settings

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user."""
    # Check if user exists
    existing = await AuthService.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create user
    user = await AuthService.create_user(
        db,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
        organization=user_data.organization,
    )
    
    # Create audit log
    audit_log = AuditLog(
        user_id=user.id,
        action=AuditAction.LOGIN,
        description="User registered",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        endpoint=str(request.url.path),
        method=request.method,
    )
    db.add(audit_log)
    
    return user


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return JWT tokens."""
    user = await AuthService.authenticate_user(
        db, login_data.email, login_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    # Update last login
    await AuthService.update_last_login(db, user)
    
    # Create tokens
    access_token = AuthService.create_access_token(
        user.id, user.email, user.is_superuser
    )
    refresh_token = AuthService.create_refresh_token(user.id)
    
    # Create audit log
    audit_log = AuditLog(
        user_id=user.id,
        action=AuditAction.LOGIN,
        description="User logged in",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        endpoint=str(request.url.path),
        method=request.method,
    )
    db.add(audit_log)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token."""
    token_data = AuthService.decode_token(refresh_token)
    
    if not token_data or not token_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    user = await AuthService.get_user_by_id(db, token_data.user_id)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Create new tokens
    access_token = AuthService.create_access_token(
        user.id, user.email, user.is_superuser
    )
    new_refresh_token = AuthService.create_refresh_token(user.id)
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
):
    """Get current user profile."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile."""
    if user_data.full_name is not None:
        current_user.full_name = user_data.full_name
    if user_data.organization is not None:
        current_user.organization = user_data.organization
    
    await db.flush()
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Change current user password."""
    # Verify current password
    if not AuthService.verify_password(
        password_data.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    # Update password
    current_user.hashed_password = AuthService.hash_password(password_data.new_password)
    await db.flush()
    
    return {"message": "Password changed successfully"}


@router.post("/api-key", response_model=dict)
async def generate_api_key(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key for the current user."""
    api_key = await AuthService.generate_user_api_key(db, current_user)
    
    return {
        "api_key": api_key,
        "message": "Store this API key securely. It won't be shown again.",
    }


@router.delete("/api-key")
async def revoke_api_key(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current user's API key."""
    current_user.api_key = None
    current_user.api_key_created_at = None
    await db.flush()
    
    return {"message": "API key revoked successfully"}
