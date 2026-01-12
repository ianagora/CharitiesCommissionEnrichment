"""Charity lookup API routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.charity_commission import CharityCommissionService
from app.api.deps import get_current_active_user
import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.get("/{charity_number}")
async def get_charity_details(
    charity_number: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get charity details from the Charity Commission API.
    
    This endpoint is used to preview charity details when confirming matches.
    """
    charity_service = CharityCommissionService()
    
    try:
        # Get full charity details including trustees
        charity_data = await charity_service.get_full_charity_details(charity_number)
        
        if not charity_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Charity {charity_number} not found",
            )
        
        # Parse and return
        parsed = CharityCommissionService.parse_charity_data(charity_data)
        
        logger.info(
            "Charity details fetched",
            charity_number=charity_number,
            user_id=str(current_user.id),
        )
        
        return parsed
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching charity details", charity_number=charity_number, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching charity details: {str(e)}",
        )
    finally:
        await charity_service.close()
