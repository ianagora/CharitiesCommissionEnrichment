"""User model for authentication."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """User model for authentication and authorization."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    organization = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # API access
    api_key = Column(String(64), unique=True, index=True, nullable=True)
    api_key_created_at = Column(DateTime, nullable=True)
    
    # Token security - version increments on password change/logout to invalidate tokens
    # Note: nullable=True for backwards compatibility with existing rows
    token_version = Column(Integer, default=0, nullable=True)
    # Track the current refresh token family (for refresh token rotation)
    refresh_token_family = Column(String(64), nullable=True, index=True)
    # Track the current valid refresh token JTI (unique ID) - only this token is valid
    current_refresh_jti = Column(String(64), nullable=True)
    
    # Two-Factor Authentication
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(32), nullable=True)  # TOTP secret key
    backup_codes = Column(Text, nullable=True)  # JSON array of backup codes
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationships
    batches = relationship("EntityBatch", back_populates="user", lazy="dynamic")
    audit_logs = relationship("AuditLog", back_populates="user", lazy="dynamic")
    
    def __repr__(self) -> str:
        return f"<User {self.email}>"
    
    def invalidate_all_tokens(self):
        """Increment token version to invalidate all existing tokens."""
        self.token_version = (self.token_version or 0) + 1
        self.refresh_token_family = None
        self.current_refresh_jti = None
