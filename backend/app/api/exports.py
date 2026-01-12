"""Export API routes."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.entity import EntityBatch
from app.models.audit import AuditLog, AuditAction
from app.schemas.entity import ExportRequest
from app.services.export_service import ExportService
from app.api.deps import get_current_active_user
import structlog
import io

logger = structlog.get_logger()

router = APIRouter()


@router.post("/excel")
async def export_to_excel(
    request: ExportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export batch data to multi-tab Excel file.
    
    Tabs included:
    - Summary: Overview and statistics
    - Entities: All entity data
    - Resolution Candidates: Matching candidates (optional)
    - Ownership Tree: Corporate relationships (optional)
    - Financial Data: Income/expenditure summary (optional)
    - Enriched Data: Trustees and subsidiaries (optional)
    """
    # Verify batch ownership
    result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == request.batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    
    # Generate export
    export_service = ExportService(db)
    
    try:
        excel_bytes = await export_service.export_batch_to_excel(
            batch_id=request.batch_id,
            include_resolutions=request.include_resolutions,
            include_ownership=request.include_ownership_tree,
            include_financial=request.include_financial_data,
            include_enriched=request.include_enriched_data,
        )
    except Exception as e:
        logger.error("Export failed", batch_id=str(request.batch_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )
    
    # Create audit log
    audit_log = AuditLog(
        user_id=current_user.id,
        action=AuditAction.EXPORT,
        resource_type="batch",
        resource_id=request.batch_id,
        description=f"Exported batch {batch.name} to Excel",
        details={
            "format": "xlsx",
            "include_resolutions": request.include_resolutions,
            "include_ownership": request.include_ownership_tree,
            "include_financial": request.include_financial_data,
            "include_enriched": request.include_enriched_data,
        },
    )
    db.add(audit_log)
    
    logger.info(
        "Batch exported",
        batch_id=str(request.batch_id),
        user_id=str(current_user.id),
        format="xlsx",
    )
    
    # Generate filename
    safe_name = "".join(c for c in batch.name if c.isalnum() or c in (' ', '-', '_')).strip()
    filename = f"{safe_name}_export.xlsx"
    
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/csv")
async def export_to_csv(
    request: ExportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Export batch data to CSV file (basic entity data only)."""
    # Verify batch ownership
    result = await db.execute(
        select(EntityBatch)
        .where(EntityBatch.id == request.batch_id)
        .where(EntityBatch.user_id == current_user.id)
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    
    # Generate export
    export_service = ExportService(db)
    
    try:
        csv_bytes = await export_service.export_to_csv(request.batch_id)
    except Exception as e:
        logger.error("Export failed", batch_id=str(request.batch_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )
    
    # Create audit log
    audit_log = AuditLog(
        user_id=current_user.id,
        action=AuditAction.EXPORT,
        resource_type="batch",
        resource_id=request.batch_id,
        description=f"Exported batch {batch.name} to CSV",
        details={"format": "csv"},
    )
    db.add(audit_log)
    
    logger.info(
        "Batch exported",
        batch_id=str(request.batch_id),
        user_id=str(current_user.id),
        format="csv",
    )
    
    # Generate filename
    safe_name = "".join(c for c in batch.name if c.isalnum() or c in (' ', '-', '_')).strip()
    filename = f"{safe_name}_export.csv"
    
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/batch/{batch_id}/quick-export")
async def quick_export(
    batch_id: UUID,
    format: str = "xlsx",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick export with default options."""
    request = ExportRequest(
        batch_id=batch_id,
        include_resolutions=True,
        include_ownership_tree=True,
        include_financial_data=True,
        include_enriched_data=True,
        format=format,
    )
    
    if format == "csv":
        return await export_to_csv(request, current_user, db)
    return await export_to_excel(request, current_user, db)
