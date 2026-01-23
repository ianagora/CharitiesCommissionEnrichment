"""Two-Factor Authentication API routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database import get_db
from app.models.user import User
from app.services.two_factor import TwoFactorService
from app.services.auth import AuthService
from app.api.deps import get_current_active_user
from pydantic import BaseModel

logger = structlog.get_logger()
router = APIRouter()


class TwoFactorSetupResponse(BaseModel):
    """Response for 2FA setup initiation."""
    qr_code: str
    backup_codes: list[str]
    message: str


class TwoFactorVerifyRequest(BaseModel):
    """Request to verify 2FA token."""
    token: str


class TwoFactorVerifyResponse(BaseModel):
    """Response after 2FA verification."""
    success: bool
    message: str


class TwoFactorDisableRequest(BaseModel):
    """Request to disable 2FA."""
    password: str
    token: str  # Either TOTP token or backup code


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate 2FA setup for the current user.
    Returns QR code and backup codes.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled for this account"
        )
    
    # Generate 2FA setup data
    setup_data = TwoFactorService.setup_2fa(current_user.email)
    
    # Store secret temporarily (not enabled yet until verified)
    current_user.two_factor_secret = setup_data["secret"]
    current_user.backup_codes = setup_data["backup_codes_json"]
    
    await db.commit()
    
    logger.info("2FA setup initiated", user_id=str(current_user.id), email=current_user.email)
    
    return TwoFactorSetupResponse(
        qr_code=setup_data["qr_code"],
        backup_codes=setup_data["backup_codes"],
        message="Scan the QR code with your authenticator app and verify with a code to enable 2FA"
    )


@router.post("/2fa/verify", response_model=TwoFactorVerifyResponse)
async def verify_and_enable_2fa(
    verify_data: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify TOTP token and enable 2FA.
    This must be called after /2fa/setup to activate 2FA.
    """
    if not current_user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please initiate 2FA setup first"
        )
    
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled"
        )
    
    # Verify the token
    is_valid = TwoFactorService.verify_totp(
        current_user.two_factor_secret,
        verify_data.token
    )
    
    if not is_valid:
        logger.warning("Invalid 2FA verification attempt", user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    # Enable 2FA
    current_user.two_factor_enabled = True
    await db.commit()
    
    logger.info("2FA enabled", user_id=str(current_user.id), email=current_user.email)
    
    return TwoFactorVerifyResponse(
        success=True,
        message="Two-factor authentication has been successfully enabled"
    )


@router.post("/2fa/disable", response_model=TwoFactorVerifyResponse)
async def disable_2fa(
    disable_data: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Disable 2FA for the current user.
    Requires password and valid 2FA token/backup code.
    """
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled for this account"
        )
    
    # Verify password
    if not AuthService.verify_password(disable_data.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    # Verify 2FA token or backup code
    token_valid = TwoFactorService.verify_totp(current_user.two_factor_secret, disable_data.token)
    
    if not token_valid and current_user.backup_codes:
        # Try backup code
        code_valid, _ = TwoFactorService.verify_backup_code(
            current_user.backup_codes,
            disable_data.token
        )
        token_valid = code_valid
    
    if not token_valid:
        logger.warning("Invalid 2FA disable attempt", user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )
    
    # Disable 2FA
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.backup_codes = None
    
    await db.commit()
    
    logger.info("2FA disabled", user_id=str(current_user.id), email=current_user.email)
    
    return TwoFactorVerifyResponse(
        success=True,
        message="Two-factor authentication has been disabled"
    )


@router.get("/2fa/status")
async def get_2fa_status(
    current_user: User = Depends(get_current_active_user),
):
    """Get 2FA status for the current user."""
    return {
        "enabled": current_user.two_factor_enabled,
        "has_backup_codes": current_user.backup_codes is not None
    }
