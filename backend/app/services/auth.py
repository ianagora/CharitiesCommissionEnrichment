"""Authentication service."""
import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.schemas.user import TokenData


class AuthService:
    """Service for authentication operations."""
    
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
    def create_access_token(cls, user_id: UUID, email: str, is_superuser: bool = False) -> str:
        """Create a JWT access token."""
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user_id),
            "email": email,
            "is_superuser": is_superuser,
            "exp": expire,
            "type": "access",
        }
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    @classmethod
    def create_refresh_token(cls, user_id: UUID) -> str:
        """Create a JWT refresh token."""
        expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "type": "refresh",
        }
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    @classmethod
    def decode_token(cls, token: str) -> Optional[TokenData]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            user_id = payload.get("sub")
            email = payload.get("email")
            is_superuser = payload.get("is_superuser", False)
            
            if user_id is None:
                return None
            
            return TokenData(
                user_id=UUID(user_id),
                email=email,
                is_superuser=is_superuser,
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
