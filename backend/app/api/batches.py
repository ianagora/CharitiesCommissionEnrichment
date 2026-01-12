"""Batch management API routes."""
import io
from typing import Optional
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.entity import Entity, EntityBatch, BatchStatus, ResolutionStatus
from app.schemas.entity import (
    EntityBatchCreate, EntityBatchResponse, EntityBatchListResponse,
    BatchProcessRequest
)
from app.services.entity_resolver import EntityResolverService
from app.services.ownership_builder import OwnershipTreeBuilder
from app.api.deps import get_current_active_user
from app.config import settings
import structlog

logger = structlog.get_logger()

router = APIRouter()


def validate_file_extension(filename: str) -> bool:
    """Validate file extension against allowed types."""
    return any(
        filename.lower().endswith(ext)
        for ext in settings.allowed_extensions_list
    )


def parse_upload_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """Parse uploaded file into DataFrame."""
    file_io = io.BytesIO(file_content)
    
    if filename.lower().endswith('.csv'):
        # Try different encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                file_io.seek(0)
                return pd.read_csv(file_io, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not decode CSV file")
    
    elif filename.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_io)
    
    else:
        raise ValueError(f"Unsupported file format: {filename}")


@router.post("", response_model=EntityBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    name_column: str = Form("name"),  # Column containing entity names
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a batch of entities from CSV or Excel file.
    
    The file should contain at least a column with entity names.
    Specify the column name using the `name_column` parameter.
    """
    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided",
        )
    
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )
    
    # Read file content
    content = await file.read()
    
    # Check file size
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB",
        )
    
    # Parse file
    try:
        df = parse_upload_file(content, file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error parsing file: {str(e)}",
        )
    
    # Validate name column exists
    if name_column not in df.columns:
        available = ", ".join(df.columns.tolist())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Column '{name_column}' not found. Available columns: {available}",
        )
    
    # Create batch
    batch = EntityBatch(
        user_id=current_user.id,
        name=name,
        description=description,
        original_filename=file.filename,
        status=BatchStatus.UPLOADED,
        total_records=len(df),
    )
    db.add(batch)
    await db.flush()
    
    # Create entities
    for idx, row in df.iterrows():
        entity_name = str(row[name_column]).strip()
        if not entity_name or entity_name == 'nan':
            continue
        
        # Store all original data
        original_data = row.to_dict()
        # Convert any non-serializable values
        for key, value in original_data.items():
            if pd.isna(value):
                original_data[key] = None
            elif hasattr(value, 'isoformat'):
                original_data[key] = value.isoformat()
        
        entity = Entity(
            batch_id=batch.id,
            original_name=entity_name,
            original_data=original_data,
            row_number=idx + 1,
            resolution_status=ResolutionStatus.PENDING,
        )
        db.add(entity)
    
    await db.flush()
    await db.refresh(batch)
    
    logger.info(
        "Batch created",
        batch_id=str(batch.id),
        user_id=str(current_user.id),
        total_records=batch.total_records,
    )
    
    return batch


@router.get("", response_model=EntityBatchListResponse)
async def list_batches(
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[BatchStatus] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all batches for the current user."""
    query = select(EntityBatch).where(EntityBatch.user_id == current_user.id)
    
    if status_filter:
        query = query.where(EntityBatch.status == status_filter)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Get paginated results
    query = query.order_by(EntityBatch.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    batches = result.scalars().all()
    
    return EntityBatchListResponse(
        batches=[EntityBatchResponse.model_validate(b) for b in batches],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{batch_id}", response_model=EntityBatchResponse)
async def get_batch(
    batch_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get batch details."""
    result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    
    return batch


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch(
    batch_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a batch and all its entities."""
    result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    
    await db.delete(batch)
    
    logger.info("Batch deleted", batch_id=str(batch_id), user_id=str(current_user.id))


async def process_batch_background(
    batch_id: UUID,
    use_ai: bool,
    build_ownership: bool,
    max_depth: int,
):
    """Background task to process a batch."""
    from app.database import get_db_context
    
    async with get_db_context() as db:
        try:
            # Process entities
            resolver = EntityResolverService(db)
            await resolver.process_batch(batch_id, use_ai=use_ai)
            
            # Build ownership trees if requested
            if build_ownership:
                builder = OwnershipTreeBuilder(db)
                await builder.build_trees_for_batch(batch_id, max_depth=max_depth)
            
            logger.info("Batch processing completed", batch_id=str(batch_id))
            
        except Exception as e:
            logger.error("Batch processing failed", batch_id=str(batch_id), error=str(e))
            # Update batch status to failed
            result = await db.execute(select(EntityBatch).where(EntityBatch.id == batch_id))
            batch = result.scalar_one_or_none()
            if batch:
                batch.status = BatchStatus.FAILED
                batch.error_message = str(e)
                await db.commit()


@router.post("/{batch_id}/process", response_model=EntityBatchResponse)
async def process_batch(
    batch_id: UUID,
    request: BatchProcessRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start processing a batch to resolve entities.
    
    This runs in the background. Poll the batch status to check progress.
    """
    result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    
    if batch.status == BatchStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch is already being processed",
        )
    
    # Update status
    batch.status = BatchStatus.PROCESSING
    await db.flush()
    
    # Start background processing
    background_tasks.add_task(
        process_batch_background,
        batch_id,
        request.use_ai_matching,
        request.build_ownership_tree,
        request.max_ownership_depth,
    )
    
    logger.info(
        "Batch processing started",
        batch_id=str(batch_id),
        user_id=str(current_user.id),
        use_ai=request.use_ai_matching,
        build_ownership=request.build_ownership_tree,
    )
    
    return batch


@router.post("/{batch_id}/reprocess")
async def reprocess_failed_entities(
    batch_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Reprocess entities that failed resolution."""
    result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    
    # Reset failed entities to pending
    from sqlalchemy import update
    await db.execute(
        update(Entity)
        .where(Entity.batch_id == batch_id)
        .where(Entity.resolution_status.in_([
            ResolutionStatus.NO_MATCH,
            ResolutionStatus.REJECTED,
        ]))
        .values(resolution_status=ResolutionStatus.PENDING)
    )
    
    # Start background processing
    background_tasks.add_task(
        process_batch_background,
        batch_id,
        True,  # use_ai
        False,  # build_ownership
        3,  # max_depth
    )
    
    return {"message": "Reprocessing started"}
