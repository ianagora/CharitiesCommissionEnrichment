"""Entity-related Pydantic schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.entity import EntityType, ResolutionStatus, BatchStatus


class EntityCreate(BaseModel):
    """Schema for creating an entity manually."""
    original_name: str = Field(..., max_length=500)
    entity_type: EntityType = EntityType.UNKNOWN
    charity_number: Optional[str] = None
    company_number: Optional[str] = None
    original_data: Optional[Dict[str, Any]] = None


class EntityUpdate(BaseModel):
    """Schema for updating an entity."""
    resolved_name: Optional[str] = None
    entity_type: Optional[EntityType] = None
    charity_number: Optional[str] = None
    company_number: Optional[str] = None
    resolution_status: Optional[ResolutionStatus] = None


class EntityResolutionResponse(BaseModel):
    """Schema for entity resolution candidate."""
    id: UUID
    charity_number: Optional[str]
    company_number: Optional[str]
    candidate_name: str
    candidate_data: Optional[Dict[str, Any]]
    confidence_score: float
    match_method: str
    is_selected: bool
    
    class Config:
        from_attributes = True


class EntityResponse(BaseModel):
    """Schema for entity response."""
    id: UUID
    batch_id: UUID
    original_name: str
    original_data: Optional[Dict[str, Any]]
    row_number: Optional[int]
    
    # Resolved data
    entity_type: EntityType
    resolved_name: Optional[str]
    charity_number: Optional[str]
    company_number: Optional[str]
    
    # Charity data
    charity_status: Optional[str]
    charity_registration_date: Optional[datetime]
    charity_activities: Optional[str]
    charity_contact_email: Optional[str]
    charity_website: Optional[str]
    charity_address: Optional[str]
    
    # Financial data
    latest_income: Optional[float]
    latest_expenditure: Optional[float]
    latest_financial_year_end: Optional[datetime]
    
    # Resolution
    resolution_status: ResolutionStatus
    resolution_confidence: Optional[float]
    resolution_method: Optional[str]
    
    # Ownership
    parent_entity_id: Optional[UUID]
    ownership_level: int
    
    # Enriched data
    enriched_data: Optional[Dict[str, Any]]
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    
    # Related resolutions
    resolutions: Optional[List[EntityResolutionResponse]] = None
    
    class Config:
        from_attributes = True


class EntityOwnershipResponse(BaseModel):
    """Schema for entity ownership relationship."""
    id: UUID
    owner_id: UUID
    owned_id: UUID
    ownership_type: Optional[str]
    ownership_percentage: Optional[float]
    relationship_description: Optional[str]
    source: Optional[str]
    verified: bool
    
    class Config:
        from_attributes = True


class OwnershipTreeNode(BaseModel):
    """Schema for ownership tree node."""
    entity: EntityResponse
    children: List["OwnershipTreeNode"] = []
    ownership_info: Optional[EntityOwnershipResponse] = None


class OwnershipTreeResponse(BaseModel):
    """Schema for complete ownership tree."""
    root: OwnershipTreeNode
    total_entities: int
    max_depth: int


class EntityBatchCreate(BaseModel):
    """Schema for creating a batch."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None


class EntityBatchResponse(BaseModel):
    """Schema for batch response."""
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    original_filename: str
    status: BatchStatus
    total_records: int
    processed_records: int
    matched_records: int
    failed_records: int
    error_message: Optional[str]
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EntityBatchListResponse(BaseModel):
    """Schema for batch list response."""
    batches: List[EntityBatchResponse]
    total: int
    page: int
    page_size: int


class BatchProcessRequest(BaseModel):
    """Schema for batch processing request."""
    batch_id: UUID
    use_ai_matching: bool = True
    build_ownership_tree: bool = False
    max_ownership_depth: int = Field(default=3, ge=1, le=10)


class ResolutionConfirmRequest(BaseModel):
    """Schema for confirming entity resolution."""
    entity_id: UUID
    resolution_id: Optional[UUID] = None  # If None, mark as no match
    charity_number: Optional[str] = None  # For manual entry
    company_number: Optional[str] = None


class ExportRequest(BaseModel):
    """Schema for export request."""
    batch_id: UUID
    include_resolutions: bool = True
    include_ownership_tree: bool = True
    include_financial_data: bool = True
    include_enriched_data: bool = True
    format: str = Field(default="xlsx", pattern="^(xlsx|csv)$")


# Update forward references
OwnershipTreeNode.model_rebuild()
