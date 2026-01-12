"""Authentication service with refresh token rotation."""
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import settings
from app.models.user import User
from app.schemas.user import TokenData

logger = structlog.get_logger()


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
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
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
    ) -> Tuple[str, str]:
        """
        Create a JWT refresh token with rotation support.
        
        Refresh token rotation:
        - Each refresh token belongs to a "family" (chain of rotated tokens)
        - When a refresh token is used, a new one is issued with the same family
        - If an old token from the same family is reused, the entire family is invalidated
        
        Returns:
            Tuple of (refresh_token, family_id)
        """
        # Generate new family ID if not provided (new login)
        if not family_id:
            family_id = secrets.token_urlsafe(32)
        
        expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "type": "refresh",
            "ver": token_version,  # Token version for invalidation
            "fam": family_id,  # Token family for rotation tracking
            "jti": secrets.token_urlsafe(16),  # Unique token ID
        }
        token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return token, family_id
    
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
            
            if user_id is None:
                return None
            
            return TokenData(
                user_id=UUID(user_id),
                email=email,
                is_superuser=is_superuser,
                token_version=token_version,
                token_family=token_family,
            )
        except JWTError:
            return None
    
    @classmethod
    def generate_api_key(cls) -> str:
        """Generate a secure API key."""
        return secrets.token_urlsafe(32)
    
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
        """Get a user by API key."""
        result = await db.execute(select(User).where(User.api_key == api_key))
        return result.scalar_one_or_none()
    
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
        user.last_login_at = datetime.utcnow()
        await db.flush()
        return user
    
    @classmethod
    async def generate_user_api_key(cls, db: AsyncSession, user: User) -> str:
        """Generate and save a new API key for a user."""
        api_key = cls.generate_api_key()
        user.api_key = api_key
        user.api_key_created_at = datetime.utcnow()
        await db.flush()
        return api_key
    
    @classmethod
    async def validate_refresh_token(
        cls,
        db: AsyncSession,
        token_data: TokenData,
    ) -> Tuple[bool, Optional[User], Optional[str]]:
        """
        Validate a refresh token and check for token reuse.
        
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
        
        # Check token family matches (for refresh token rotation)
        if token_data.token_family:
            if user.refresh_token_family and user.refresh_token_family != token_data.token_family:
                # Different family - this is a reused old token!
                logger.error(
                    "Refresh token reuse detected - invalidating all tokens",
                    user_id=str(user.id),
                    token_family=token_data.token_family,
                    current_family=user.refresh_token_family,
                )
                # Invalidate all tokens for this user (security measure)
                user.invalidate_all_tokens()
                await db.flush()
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
        
        Updates the user's refresh_token_family to track the current valid family.
        
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
        refresh_token, family_id = cls.create_refresh_token(
            user.id,
            token_version,
            old_family,  # Keep same family for rotation
        )
        
        # Update user's current family
        user.refresh_token_family = family_id
        await db.flush()
        
        logger.info(
            "Token rotation completed",
            user_id=str(user.id),
            family_id=family_id[:8] + "...",
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
