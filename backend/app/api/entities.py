"""Entity management API routes."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.entity import Entity, EntityBatch, EntityResolution, ResolutionStatus
from app.schemas.entity import (
    EntityResponse, EntityUpdate, EntityResolutionResponse,
    ResolutionConfirmRequest, OwnershipTreeResponse
)
from app.services.entity_resolver import EntityResolverService
from app.services.ownership_builder import OwnershipTreeBuilder
from app.api.deps import get_current_active_user
import structlog
import sys
import traceback

logger = structlog.get_logger()

router = APIRouter()


@router.get("/batch/{batch_id}", response_model=List[EntityResponse])
async def list_entities_in_batch(
    batch_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: Optional[ResolutionStatus] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all entities in a batch."""
    # Verify batch ownership
    batch_result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    batch = batch_result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    
    # Build query
    query = (
        select(Entity)
        .where(Entity.batch_id == batch_id)
        .options(selectinload(Entity.resolutions))
    )
    
    if status_filter:
        query = query.where(Entity.resolution_status == status_filter)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (Entity.original_name.ilike(search_pattern)) |
            (Entity.resolved_name.ilike(search_pattern)) |
            (Entity.charity_number.ilike(search_pattern))
        )
    
    query = query.order_by(Entity.row_number)
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    entities = result.scalars().all()
    
    print(f"[DEBUG] Found {len(entities)} entities", file=sys.stderr, flush=True)
    
    try:
        responses = []
        for e in entities:
            print(f"[DEBUG] Converting entity: id={e.id}, name={e.original_name}, type={e.entity_type}, status={e.resolution_status}", file=sys.stderr, flush=True)
            try:
                response = EntityResponse.model_validate(e)
                responses.append(response)
            except Exception as convert_err:
                print(f"[DEBUG] Error converting entity {e.id}: {type(convert_err).__name__}: {convert_err}", file=sys.stderr, flush=True)
                print(f"[DEBUG] Entity data: entity_type={e.entity_type}, resolution_status={e.resolution_status}", file=sys.stderr, flush=True)
                raise
        return responses
    except Exception as e:
        print(f"[DEBUG] Error building response: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        print(f"[DEBUG] Traceback: {traceback.format_exc()}", file=sys.stderr, flush=True)
        raise


@router.get("/batch/{batch_id}/stats")
async def get_batch_statistics(
    batch_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for a batch."""
    # Verify batch ownership
    batch_result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    batch = batch_result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    
    # Get status counts
    status_query = (
        select(Entity.resolution_status, func.count())
        .where(Entity.batch_id == batch_id)
        .group_by(Entity.resolution_status)
    )
    status_result = await db.execute(status_query)
    status_counts = {str(status.value): count for status, count in status_result.all()}
    
    # Get type counts
    type_query = (
        select(Entity.entity_type, func.count())
        .where(Entity.batch_id == batch_id)
        .group_by(Entity.entity_type)
    )
    type_result = await db.execute(type_query)
    type_counts = {str(etype.value) if etype else "unknown": count for etype, count in type_result.all()}
    
    # Get financial summary
    financial_query = (
        select(
            func.sum(Entity.latest_income),
            func.sum(Entity.latest_expenditure),
            func.count().filter(Entity.latest_income.isnot(None))
        )
        .where(Entity.batch_id == batch_id)
    )
    financial_result = await db.execute(financial_query)
    total_income, total_expenditure, entities_with_financials = financial_result.one()
    
    return {
        "batch_id": str(batch_id),
        "status_breakdown": status_counts,
        "type_breakdown": type_counts,
        "financial_summary": {
            "total_income": total_income or 0,
            "total_expenditure": total_expenditure or 0,
            "entities_with_financials": entities_with_financials or 0,
        },
        "total_entities": sum(status_counts.values()),
    }


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get entity details."""
    result = await db.execute(
        select(Entity)
        .options(selectinload(Entity.resolutions))
        .where(Entity.id == entity_id)
    )
    entity = result.scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    # Verify ownership through batch
    batch_result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == entity.batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    if not batch_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    return EntityResponse.model_validate(entity)


@router.patch("/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: UUID,
    update_data: EntityUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update entity details."""
    result = await db.execute(
        select(Entity)
        .options(selectinload(Entity.resolutions))
        .where(Entity.id == entity_id)
    )
    entity = result.scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    # Verify ownership through batch
    batch_result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == entity.batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    if not batch_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(entity, key, value)
    
    await db.flush()
    return EntityResponse.model_validate(entity)


@router.get("/{entity_id}/resolutions", response_model=List[EntityResolutionResponse])
async def get_entity_resolutions(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all resolution candidates for an entity."""
    # Verify entity access
    entity_result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = entity_result.scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    batch_result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == entity.batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    if not batch_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    # Get resolutions
    result = await db.execute(
        select(EntityResolution)
        .where(EntityResolution.entity_id == entity_id)
        .order_by(EntityResolution.confidence_score.desc())
    )
    resolutions = result.scalars().all()
    
    return [EntityResolutionResponse.model_validate(r) for r in resolutions]


@router.post("/{entity_id}/confirm", response_model=EntityResponse)
async def confirm_entity_resolution(
    entity_id: UUID,
    request: ResolutionConfirmRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm entity resolution - either from candidates or manual entry.
    
    Provide either:
    - `resolution_id`: ID of the resolution candidate to confirm
    - `charity_number`: Manual charity number entry
    - Neither: Mark as no match/rejected
    """
    # Verify entity access
    entity_result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = entity_result.scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    batch_result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == entity.batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    if not batch_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    # Confirm resolution
    resolver = EntityResolverService(db)
    try:
        entity = await resolver.confirm_resolution(
            entity_id=entity_id,
            resolution_id=request.resolution_id,
            charity_number=request.charity_number,
        )
    finally:
        await resolver.close()
    
    # Refresh with resolutions
    result = await db.execute(
        select(Entity)
        .options(selectinload(Entity.resolutions))
        .where(Entity.id == entity_id)
    )
    entity = result.scalar_one()
    
    logger.info(
        "Entity resolution confirmed",
        entity_id=str(entity_id),
        user_id=str(current_user.id),
        charity_number=entity.charity_number,
    )
    
    return EntityResponse.model_validate(entity)


@router.post("/{entity_id}/re-resolve", response_model=EntityResponse)
async def re_resolve_entity(
    entity_id: UUID,
    use_ai: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-attempt resolution for a single entity."""
    # Verify entity access
    result = await db.execute(
        select(Entity)
        .options(selectinload(Entity.resolutions))
        .where(Entity.id == entity_id)
    )
    entity = result.scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    batch_result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == entity.batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    if not batch_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    # Reset entity status
    entity.resolution_status = ResolutionStatus.PENDING
    entity.resolved_name = None
    entity.charity_number = None
    entity.resolution_confidence = None
    
    # Clear existing resolutions
    await db.execute(
        select(EntityResolution)
        .where(EntityResolution.entity_id == entity_id)
    )
    
    # Re-resolve
    resolver = EntityResolverService(db)
    try:
        entity = await resolver.resolve_entity(entity, use_ai=use_ai)
    finally:
        await resolver.close()
    
    # Refresh with resolutions
    result = await db.execute(
        select(Entity)
        .options(selectinload(Entity.resolutions))
        .where(Entity.id == entity_id)
    )
    entity = result.scalar_one()
    
    return EntityResponse.model_validate(entity)


@router.get("/{entity_id}/ownership-tree")
async def get_entity_ownership_tree(
    entity_id: UUID,
    max_depth: int = Query(3, ge=1, le=10),
    direction: str = Query("both", pattern="^(up|down|both)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ownership tree for an entity."""
    # Verify entity access
    entity_result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = entity_result.scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    batch_result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == entity.batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    if not batch_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    # Build tree
    builder = OwnershipTreeBuilder(db)
    try:
        tree = await builder.build_tree_for_entity(
            entity_id=entity_id,
            max_depth=max_depth,
            direction=direction,
        )
    finally:
        await builder.close()
    
    return tree


@router.post("/{entity_id}/build-ownership-tree")
async def build_entity_ownership_tree(
    entity_id: UUID,
    max_depth: int = Query(3, ge=1, le=10),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Build and save ownership tree for an entity."""
    # Verify entity access
    entity_result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = entity_result.scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    batch_result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == entity.batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    if not batch_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    if entity.resolution_status not in (ResolutionStatus.MATCHED, ResolutionStatus.CONFIRMED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity must be matched before building ownership tree",
        )
    
    # Build tree
    builder = OwnershipTreeBuilder(db)
    try:
        tree = await builder.build_tree_for_entity(
            entity_id=entity_id,
            max_depth=max_depth,
            direction="down",
        )
    finally:
        await builder.close()
    
    logger.info(
        "Ownership tree built",
        entity_id=str(entity_id),
        user_id=str(current_user.id),
        total_entities=tree.get("total_entities", 0),
    )
    
    return tree
