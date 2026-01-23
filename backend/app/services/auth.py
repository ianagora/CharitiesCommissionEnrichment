"""Authentication service with refresh token rotation."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import settings
from app.models.user import User, API_KEY_PREFIX_LENGTH, TOKEN_FAMILY_LENGTH, TOKEN_JTI_LENGTH
from app.schemas.user import TokenData

logger = structlog.get_logger()

# Constants
API_KEY_LENGTH = 32


class AuthService:
    """Service for authentication operations with secure token management."""
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash."""
        return cls.pwd_context.verify(plain_password, hashed_password)
    
    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash a password."""
        return cls.pwd_context.hash(password)
    
    @classmethod
    def create_access_token(
        cls,
        user_id: UUID,
        email: str,
        is_superuser: bool = False,
        token_version: int = 0,
    ) -> str:
        """
        Create a JWT access token.
        
        The token includes a version number that must match the user's
        current token_version for the token to be valid.
        """
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user_id),
            "email": email,
            "is_superuser": is_superuser,
            "exp": expire,
            "type": "access",
            "ver": token_version,  # Token version for invalidation
        }
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    @classmethod
    def create_refresh_token(
        cls,
        user_id: UUID,
        token_version: int = 0,
        family_id: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """
        Create a JWT refresh token with rotation support.
        
        Refresh token rotation:
        - Each refresh token belongs to a "family" (chain of rotated tokens)
        - Each token has a unique JTI (token ID)
        - Only the most recent token (tracked by JTI) is valid
        - If an old token is reused, all tokens are invalidated (security measure)
        
        Returns:
            Tuple of (refresh_token, family_id, jti)
        """
        # Generate new family ID if not provided (new login)
        if not family_id:
            family_id = secrets.token_urlsafe(TOKEN_FAMILY_LENGTH)
        
        # Generate unique token ID for this specific token
        jti = secrets.token_urlsafe(TOKEN_JTI_LENGTH)
        
        expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "type": "refresh",
            "ver": token_version,  # Token version for invalidation
            "fam": family_id,  # Token family for rotation tracking
            "jti": jti,  # Unique token ID - only this token is valid
        }
        token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return token, family_id, jti
    
    @classmethod
    def decode_token(cls, token: str) -> Optional[TokenData]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            user_id = payload.get("sub")
            email = payload.get("email")
            is_superuser = payload.get("is_superuser", False)
            token_version = payload.get("ver", 0)
            token_family = payload.get("fam")
            token_jti = payload.get("jti")  # Unique token ID
            
            if user_id is None:
                return None
            
            return TokenData(
                user_id=UUID(user_id),
                email=email,
                is_superuser=is_superuser,
                token_version=token_version,
                token_family=token_family,
                token_jti=token_jti,
            )
        except JWTError:
            return None
    
    @classmethod
    def generate_api_key(cls) -> Tuple[str, str, str]:
        """
        Generate a secure API key.
        
        Returns:
            Tuple of (full_key, key_hash, key_prefix)
        """
        full_key = secrets.token_urlsafe(API_KEY_LENGTH)
        key_hash = cls.pwd_context.hash(full_key)
        key_prefix = full_key[:API_KEY_PREFIX_LENGTH]
        return full_key, key_hash, key_prefix
    
    @classmethod
    def verify_api_key(cls, plain_key: str, hashed_key: str) -> bool:
        """Verify an API key against its hash."""
        return cls.pwd_context.verify(plain_key, hashed_key)
    
    @classmethod
    async def get_user_by_email(cls, db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by email."""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_user_by_id(cls, db: AsyncSession, user_id: UUID) -> Optional[User]:
        """Get a user by ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_user_by_api_key(cls, db: AsyncSession, api_key: str) -> Optional[User]:
        """
        Get a user by API key.
        
        First filters by prefix for efficiency, then verifies the full hash.
        """
        if not api_key or len(api_key) < API_KEY_PREFIX_LENGTH:
            return None
        
        key_prefix = api_key[:API_KEY_PREFIX_LENGTH]
        
        # Find users with matching prefix
        result = await db.execute(
            select(User).where(User.api_key_prefix == key_prefix)
        )
        users = result.scalars().all()
        
        # Verify the full key hash for each candidate
        for user in users:
            if user.api_key_hash and cls.verify_api_key(api_key, user.api_key_hash):
                return user
        
        return None
    
    @classmethod
    async def authenticate_user(cls, db: AsyncSession, email: str, password: str) -> Optional[User]:
        """Authenticate a user with email and password."""
        user = await cls.get_user_by_email(db, email)
        if not user:
            return None
        if not cls.verify_password(password, user.hashed_password):
            return None
        return user
    
    @classmethod
    async def create_user(
        cls,
        db: AsyncSession,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        organization: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        user = User(
            email=email,
            hashed_password=cls.hash_password(password),
            full_name=full_name,
            organization=organization,
            token_version=0,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user
    
    @classmethod
    async def update_last_login(cls, db: AsyncSession, user: User) -> User:
        """Update user's last login timestamp."""
        user.last_login_at = datetime.now(timezone.utc)
        await db.flush()
        return user
    
    @classmethod
    async def generate_user_api_key(cls, db: AsyncSession, user: User) -> str:
        """
        Generate and save a new API key for a user.
        
        Returns the full API key (only shown once - not stored in plain text).
        """
        full_key, key_hash, key_prefix = cls.generate_api_key()
        user.api_key_hash = key_hash
        user.api_key_prefix = key_prefix
        user.api_key_created_at = datetime.now(timezone.utc)
        await db.flush()
        return full_key  # Return the full key - user must save it
    
    @classmethod
    async def validate_refresh_token(
        cls,
        db: AsyncSession,
        token_data: TokenData,
    ) -> Tuple[bool, Optional[User], Optional[str]]:
        """
        Validate a refresh token and check for token reuse.
        
        Implements strict refresh token rotation:
        - Only the most recently issued refresh token is valid
        - Reuse of any old token invalidates all tokens (security measure)
        
        Returns:
            Tuple of (is_valid, user, error_message)
        """
        if not token_data or not token_data.user_id:
            return False, None, "Invalid token"
        
        user = await cls.get_user_by_id(db, token_data.user_id)
        if not user:
            return False, None, "User not found"
        
        if not user.is_active:
            return False, None, "User account is inactive"
        
        # Check token version matches (tokens invalidated on password change/logout)
        user_token_version = user.token_version or 0
        token_version = token_data.token_version or 0
        
        if token_version != user_token_version:
            logger.warning(
                "Token version mismatch - possible token reuse after logout/password change",
                user_id=str(user.id),
                token_version=token_version,
                user_token_version=user_token_version,
            )
            return False, None, "Token has been invalidated"
        
        # Check token JTI matches the current valid token
        # This is the key check for refresh token rotation - only ONE token is valid
        if token_data.token_jti:
            if user.current_refresh_jti and user.current_refresh_jti != token_data.token_jti:
                # Different JTI - this is an old/reused token!
                logger.error(
                    "Refresh token reuse detected - invalidating all tokens",
                    user_id=str(user.id),
                    token_jti=token_data.token_jti[:8] + "..." if token_data.token_jti else None,
                    current_jti=user.current_refresh_jti[:8] + "..." if user.current_refresh_jti else None,
                )
                # Invalidate all tokens for this user (security measure)
                user.invalidate_all_tokens()
                await db.flush()
                await db.commit()  # CRITICAL: Commit to persist the invalidation
                return False, None, "Token reuse detected - all sessions invalidated"
        
        # Also check token family for additional security
        if token_data.token_family:
            if user.refresh_token_family and user.refresh_token_family != token_data.token_family:
                logger.error(
                    "Refresh token family mismatch - invalidating all tokens",
                    user_id=str(user.id),
                    token_family=token_data.token_family[:8] + "..." if token_data.token_family else None,
                    current_family=user.refresh_token_family[:8] + "..." if user.refresh_token_family else None,
                )
                user.invalidate_all_tokens()
                await db.flush()
                await db.commit()  # CRITICAL: Commit to persist the invalidation
                return False, None, "Token reuse detected - all sessions invalidated"
        
        return True, user, None
    
    @classmethod
    async def rotate_refresh_token(
        cls,
        db: AsyncSession,
        user: User,
        old_family: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """
        Issue new access and refresh tokens with rotation.
        
        Updates the user's refresh_token_family and current_refresh_jti to track
        the only valid refresh token.
        
        Returns:
            Tuple of (access_token, refresh_token, family_id)
        """
        token_version = user.token_version or 0
        
        # Create new access token
        access_token = cls.create_access_token(
            user.id,
            user.email,
            user.is_superuser,
            token_version,
        )
        
        # Create new refresh token (same family if rotating, new family if fresh login)
        refresh_token, family_id, jti = cls.create_refresh_token(
            user.id,
            token_version,
            old_family,  # Keep same family for rotation
        )
        
        # Update user's current family and JTI (only this token is now valid)
        user.refresh_token_family = family_id
        user.current_refresh_jti = jti
        await db.flush()
        
        logger.info(
            "Token rotation completed",
            user_id=str(user.id),
            family_id=family_id[:8] + "...",
            jti=jti[:8] + "...",
        )
        
        return access_token, refresh_token, family_id
    
    @classmethod
    async def logout_user(cls, db: AsyncSession, user: User) -> None:
        """
        Logout user by invalidating all tokens.
        
        Increments token_version which invalidates all existing access tokens,
        and clears refresh_token_family which invalidates all refresh tokens.
        """
        user.invalidate_all_tokens()
        await db.flush()
        
        logger.info("User logged out - all tokens invalidated", user_id=str(user.id))
