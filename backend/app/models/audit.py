"""Audit logging model."""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AuditAction(str, Enum):
    """Types of auditable actions."""
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    BATCH_UPLOAD = "batch_upload"
    BATCH_PROCESS = "batch_process"
    ENTITY_RESOLVE = "entity_resolve"
    ENTITY_CONFIRM = "entity_confirm"
    ENTITY_REJECT = "entity_reject"
    OWNERSHIP_BUILD = "ownership_build"
    EXPORT = "export"
    API_CALL = "api_call"
    ERROR = "error"


class AuditLog(Base):
    """Audit log for tracking user actions."""
    
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Action details
    action = Column(SQLEnum(AuditAction), nullable=False)
    resource_type = Column(String(100), nullable=True)  # "batch", "entity", etc.
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Request info
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    endpoint = Column(String(255), nullable=True)
    method = Column(String(10), nullable=True)
    
    # Details
    description = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    
    # Status
    success = Column(String(10), default="success", nullable=False)  # "success", "failure"
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.user_id}>"
