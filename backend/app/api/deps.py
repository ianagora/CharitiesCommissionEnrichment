"""API dependencies for authentication and authorization."""
from typing import Optional
from uuid import UUID
import structlog

from fastapi import Depends, HTTPException, status, Request
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

# Endpoints that are exempt from mandatory 2FA enforcement.
# MFA setup now happens during login (no token issued until MFA is complete),
# so only status, profile, and logout need exemptions for defence-in-depth.
TWO_FACTOR_EXEMPT_PATHS = {
    "/api/v1/auth/2fa/status",
    "/api/v1/auth/me",
    "/api/v1/auth/logout",
}


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token or API key.

    Validates token version to ensure tokens haven't been invalidated
    by logout or password change.

    Enforces 2FA completion: if a user has 2FA enabled but hasn't completed
    verification (indicated by two_factor_enabled being True on the user),
    access is only granted to 2FA-related endpoints.

    Raises:
        HTTPException: If authentication fails
    """
    user = None
    token_scope = "full"  # Default scope (used for API key auth)

    # Try JWT token first
    if credentials:
        token_data = AuthService.decode_token(credentials.credentials)
        if token_data and token_data.user_id:
            token_scope = token_data.scope or "full"
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
            else:
                user = None

    # Try API key
    if not user and api_key:
        user = await AuthService.get_user_by_api_key(db, api_key)
        if user and not user.is_active:
            user = None
        token_scope = "full"  # API keys always have full scope

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Defense-in-depth: block access if 2FA is not enabled, regardless of token scope.
    # MFA setup now happens during login (no token is issued until MFA is complete),
    # so this should not trigger in normal operation — it catches edge cases only.
    request_path = request.url.path
    if not user.two_factor_enabled and request_path not in TWO_FACTOR_EXEMPT_PATHS:
        logger.warning(
            "Access blocked - 2FA setup not completed (defense-in-depth)",
            user_id=str(user.id),
            path=request_path,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Two-factor authentication setup is required before accessing this resource.",
            headers={"X-Require-2FA-Setup": "true"},
        )

    return user


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
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.
    """
    try:
        return await get_current_user(request, credentials, api_key, db)
    except HTTPException:
        return None
