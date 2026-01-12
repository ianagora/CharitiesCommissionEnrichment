"""API dependencies for authentication and authorization."""
from typing import Optional
from uuid import UUID
import structlog

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth import AuthService
from app.config import settings

logger = structlog.get_logger()

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token or API key.
    
    Validates token version to ensure tokens haven't been invalidated
    by logout or password change.
    
    Raises:
        HTTPException: If authentication fails
    """
    # Try JWT token first
    if credentials:
        token_data = AuthService.decode_token(credentials.credentials)
        if token_data and token_data.user_id:
            user = await AuthService.get_user_by_id(db, token_data.user_id)
            if user and user.is_active:
                # Verify token version matches (for logout/password change invalidation)
                user_token_version = user.token_version or 0
                token_version = token_data.token_version or 0
                
                if token_version != user_token_version:
                    logger.warning(
                        "Token version mismatch - token invalidated",
                        user_id=str(user.id),
                        token_version=token_version,
                        user_token_version=user_token_version,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has been invalidated. Please log in again.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                
                return user
    
    # Try API key
    if api_key:
        user = await AuthService.get_user_by_api_key(db, api_key)
        if user and user.is_active:
            return user
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current active user.
    
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get the current superuser.
    
    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.
    """
    try:
        return await get_current_user(credentials, api_key, db)
    except HTTPException:
        return None
