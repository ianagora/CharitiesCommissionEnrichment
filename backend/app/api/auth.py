"""Authentication API routes with refresh token rotation."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
import structlog

from app.database import get_db
from app.models.user import User
from app.models.audit import AuditLog, AuditAction
from app.schemas.user import (
    UserCreate, UserResponse, UserLogin, UserUpdate,
    Token, TokenWithRefresh, PasswordChange
)
from app.services.auth import AuthService
from app.services.rate_limit import login_rate_limiter
from app.api.deps import get_current_active_user
from app.config import settings

logger = structlog.get_logger()
router = APIRouter()

# Rate limiter for registration
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")  # Prevent spam account creation
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user."""
    # Check if user exists - use generic message to prevent enumeration
    existing = await AuthService.get_user_by_email(db, user_data.email)
    if existing:
        # Log the attempt but return generic message
        logger.warning(
            "Registration attempt with existing email",
            ip=request.client.host if request.client else None
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Please check your information or contact support.",
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
    
    return UserResponse.from_user(user)


# Constants for secure cookie settings
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_COOKIE_PATH = "/api/v1/auth"


def set_refresh_token_cookie(response: Response, refresh_token: str, max_age: int) -> None:
    """Set refresh token in a secure httpOnly cookie."""
    from app.config import settings
    
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        httponly=True,  # Not accessible by JavaScript - prevents XSS token theft
        secure=not settings.DEBUG,  # HTTPS only in production
        samesite="strict",  # Strict CSRF protection
        path=REFRESH_TOKEN_COOKIE_PATH,  # Only sent to auth endpoints
    )


def clear_refresh_token_cookie(response: Response) -> None:
    """Clear the refresh token cookie."""
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path=REFRESH_TOKEN_COOKIE_PATH,
    )


@router.post("/login")
async def login(
    login_data: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return JWT tokens with rotation support."""
    client_ip = request.client.host if request.client else None
    
    # Check if account is locked due to too many failed attempts
    is_locked, seconds_remaining = await login_rate_limiter.is_locked(
        login_data.email, client_ip
    )
    if is_locked:
        logger.warning(
            "Login attempt on locked account",
            email=login_data.email,
            ip=client_ip,
            seconds_remaining=seconds_remaining,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked. Try again in {seconds_remaining} seconds.",
            headers={"Retry-After": str(seconds_remaining)},
        )
    
    # Attempt authentication
    user = await AuthService.authenticate_user(
        db, login_data.email, login_data.password
    )
    
    if not user:
        # Record failed attempt
        is_now_locked, attempts_remaining = await login_rate_limiter.record_failed_attempt(
            login_data.email, client_ip
        )
        
        # Create failed login audit log
        audit_log = AuditLog(
            action=AuditAction.LOGIN,
            description=f"Failed login attempt - {'account locked' if is_now_locked else f'{attempts_remaining} attempts remaining'}",
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            endpoint=str(request.url.path),
            method=request.method,
            details={"email": login_data.email, "locked": is_now_locked},
        )
        db.add(audit_log)
        await db.commit()
        
        if is_now_locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Account locked for {settings.LOGIN_LOCKOUT_MINUTES} minutes.",
                headers={"Retry-After": str(settings.LOGIN_LOCKOUT_MINUTES * 60)},
            )
        
        # Use constant-time comparison message to prevent user enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    # Check if 2FA is enabled
    if user.two_factor_enabled:
        if not login_data.totp_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="2FA code required",
                headers={"X-Require-2FA": "true"},
            )
        
        # Import here to avoid circular dependency
        from app.services.two_factor import TwoFactorService
        
        # Try TOTP first
        totp_valid = TwoFactorService.verify_totp(
            user.two_factor_secret,
            login_data.totp_code
        )
        
        # If TOTP fails, try backup code
        if not totp_valid and user.backup_codes:
            code_valid, updated_codes = TwoFactorService.verify_backup_code(
                user.backup_codes,
                login_data.totp_code
            )
            
            if code_valid:
                # Update backup codes (remove used code)
                user.backup_codes = updated_codes
                await db.commit()
                logger.info(
                    "Backup code used for login",
                    user_id=str(user.id),
                    email=user.email
                )
            else:
                # Both TOTP and backup code failed
                logger.warning(
                    "Invalid 2FA code during login",
                    user_id=str(user.id),
                    email=user.email,
                    ip=client_ip
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid 2FA code",
                )
        elif not totp_valid:
            # TOTP failed and no backup codes available
            logger.warning(
                "Invalid 2FA code during login",
                user_id=str(user.id),
                email=user.email,
                ip=client_ip
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code",
            )
    
    # Successful login - clear any failed attempts
    await login_rate_limiter.record_successful_login(login_data.email, client_ip)
    
    # Update last login
    await AuthService.update_last_login(db, user)
    
    # Create tokens with rotation (new token family for fresh login)
    access_token, refresh_token, _ = await AuthService.rotate_refresh_token(db, user)
    
    # Create audit log
    audit_log = AuditLog(
        user_id=user.id,
        action=AuditAction.LOGIN,
        description="User logged in successfully",
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
        endpoint=str(request.url.path),
        method=request.method,
    )
    db.add(audit_log)
    
    # Set refresh token in httpOnly cookie (secure, not accessible by JS)
    cookie_max_age = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    set_refresh_token_cookie(response, refresh_token, cookie_max_age)
    
    # Return only access token in response body
    return Token(
        access_token=access_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token_body: str = None,  # Optional body param for backwards compatibility
):
    """
    Refresh access token using refresh token with rotation.
    
    The refresh token can be provided via:
    1. httpOnly cookie (preferred, more secure)
    2. Request body (for backwards compatibility)
    
    Implements refresh token rotation:
    - Each refresh issues a new refresh token
    - Old refresh tokens become invalid
    - Reuse of old tokens invalidates the entire token family
    """
    # Get refresh token from cookie first, then fall back to body
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME) or refresh_token_body
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )
    
    token_data = AuthService.decode_token(refresh_token)
    
    if not token_data or not token_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    # Validate the refresh token (checks version and family)
    is_valid, user, error = await AuthService.validate_refresh_token(db, token_data)
    
    if not is_valid:
        logger.warning(
            "Refresh token validation failed",
            error=error,
            ip=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid refresh token",
        )
    
    # Rotate tokens (issue new tokens, same family)
    access_token, new_refresh_token, _ = await AuthService.rotate_refresh_token(
        db, user, token_data.token_family
    )
    
    # Update refresh token cookie
    cookie_max_age = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    set_refresh_token_cookie(response, new_refresh_token, cookie_max_age)
    
    return Token(
        access_token=access_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout user and invalidate all tokens.
    
    This increments the user's token_version, which invalidates:
    - All existing access tokens
    - All existing refresh tokens
    - Clears the refresh token cookie
    """
    await AuthService.logout_user(db, current_user)
    
    # Clear refresh token cookie
    clear_refresh_token_cookie(response)
    
    # Create audit log
    audit_log = AuditLog(
        user_id=current_user.id,
        action=AuditAction.LOGOUT,
        description="User logged out - all tokens invalidated",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        endpoint=str(request.url.path),
        method=request.method,
    )
    db.add(audit_log)
    
    return {"message": "Logged out successfully. All sessions have been invalidated."}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
):
    """Get current user profile."""
    return UserResponse.from_user(current_user)


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
    return UserResponse.from_user(current_user)


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change current user password.
    
    This also invalidates all existing tokens, requiring re-login.
    """
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
    
    # Invalidate all existing tokens (security best practice)
    current_user.invalidate_all_tokens()
    
    await db.flush()
    
    # Create audit log
    audit_log = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PASSWORD_CHANGE,
        description="Password changed - all tokens invalidated",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        endpoint=str(request.url.path),
        method=request.method,
    )
    db.add(audit_log)
    
    return {"message": "Password changed successfully. Please log in again."}


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
    current_user.api_key_hash = None
    current_user.api_key_prefix = None
    current_user.api_key_created_at = None
    await db.flush()
    
    return {"message": "API key revoked successfully"}
