"""Entity models for charity data management."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SQLEnum, Float, ForeignKey,
    Integer, JSON, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class EntityType(str, Enum):
    """Types of entities."""
    CHARITY = "charity"
    COMPANY = "company"
    TRUST = "trust"
    CIO = "cio"  # Charitable Incorporated Organisation
    UNKNOWN = "unknown"


class ResolutionStatus(str, Enum):
    """Entity resolution status."""
    PENDING = "pending"
    MATCHED = "matched"
    MULTIPLE_MATCHES = "multiple_matches"
    NO_MATCH = "no_match"
    MANUAL_REVIEW = "manual_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class BatchStatus(str, Enum):
    """Batch processing status."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class EntityBatch(Base):
    """Batch of uploaded entities for processing."""
    
    __tablename__ = "entity_batches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Batch info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    original_filename = Column(String(255), nullable=False)
    
    # Status
    status = Column(SQLEnum(BatchStatus), default=BatchStatus.UPLOADED, nullable=False)
    total_records = Column(Integer, default=0, nullable=False)
    processed_records = Column(Integer, default=0, nullable=False)
    matched_records = Column(Integer, default=0, nullable=False)
    failed_records = Column(Integer, default=0, nullable=False)
    
    # Processing info
    error_message = Column(Text, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="batches")
    entities = relationship("Entity", back_populates="batch", lazy="dynamic", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<EntityBatch {self.name} ({self.status})>"


class Entity(Base):
    """Entity record - could be a charity, company, or other organization."""
    
    __tablename__ = "entities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("entity_batches.id"), nullable=False)
    
    # Original uploaded data
    original_name = Column(String(500), nullable=False)
    original_data = Column(JSON, nullable=True)  # Store all original CSV/Excel columns
    row_number = Column(Integer, nullable=True)
    
    # Resolved entity data
    entity_type = Column(SQLEnum(EntityType), default=EntityType.UNKNOWN, nullable=False)
    resolved_name = Column(String(500), nullable=True)
    charity_number = Column(String(50), index=True, nullable=True)
    company_number = Column(String(50), index=True, nullable=True)
    
    # Charity Commission data
    charity_status = Column(String(100), nullable=True)
    charity_registration_date = Column(DateTime, nullable=True)
    charity_removal_date = Column(DateTime, nullable=True)
    charity_activities = Column(Text, nullable=True)
    charity_contact_email = Column(String(255), nullable=True)
    charity_contact_phone = Column(String(50), nullable=True)
    charity_website = Column(String(500), nullable=True)
    charity_address = Column(Text, nullable=True)
    
    # Financial data
    latest_income = Column(Float, nullable=True)
    latest_expenditure = Column(Float, nullable=True)
    latest_financial_year_end = Column(DateTime, nullable=True)
    
    # Resolution
    resolution_status = Column(SQLEnum(ResolutionStatus), default=ResolutionStatus.PENDING, nullable=False)
    resolution_confidence = Column(Float, nullable=True)  # 0-1 confidence score
    resolution_method = Column(String(50), nullable=True)  # "exact_match", "fuzzy_match", "ai_match"
    
    # Ownership tree
    parent_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=True)
    ownership_level = Column(Integer, default=0, nullable=False)  # 0 = root
    
    # Enriched data (from AI or additional APIs)
    enriched_data = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships
    batch = relationship("EntityBatch", back_populates="entities")
    parent = relationship("Entity", remote_side=[id], backref="children")
    resolutions = relationship("EntityResolution", back_populates="entity", lazy="dynamic", cascade="all, delete-orphan")
    ownerships_as_owner = relationship("EntityOwnership", foreign_keys="EntityOwnership.owner_id", back_populates="owner", lazy="dynamic")
    ownerships_as_owned = relationship("EntityOwnership", foreign_keys="EntityOwnership.owned_id", back_populates="owned", lazy="dynamic")
    
    def __repr__(self) -> str:
        return f"<Entity {self.original_name} ({self.resolution_status})>"


class EntityResolution(Base):
    """Candidate matches for entity resolution."""
    
    __tablename__ = "entity_resolutions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    
    # Candidate data
    charity_number = Column(String(50), nullable=True)
    company_number = Column(String(50), nullable=True)
    candidate_name = Column(String(500), nullable=False)
    candidate_data = Column(JSON, nullable=True)
    
    # Matching info
    confidence_score = Column(Float, nullable=False)
    match_method = Column(String(50), nullable=False)
    is_selected = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    entity = relationship("Entity", back_populates="resolutions")
    
    def __repr__(self) -> str:
        return f"<EntityResolution {self.candidate_name} ({self.confidence_score})>"


class EntityOwnership(Base):
    """Ownership relationships between entities."""
    
    __tablename__ = "entity_ownerships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    owned_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    
    # Ownership details
    ownership_type = Column(String(100), nullable=True)  # "trustee", "subsidiary", "related"
    ownership_percentage = Column(Float, nullable=True)
    relationship_description = Column(Text, nullable=True)
    
    # Source of information
    source = Column(String(100), nullable=True)  # "charity_commission", "companies_house", "manual"
    verified = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    owner = relationship("Entity", foreign_keys=[owner_id], back_populates="ownerships_as_owner")
    owned = relationship("Entity", foreign_keys=[owned_id], back_populates="ownerships_as_owned")
    
    def __repr__(self) -> str:
        return f"<EntityOwnership {self.owner_id} -> {self.owned_id}>"
