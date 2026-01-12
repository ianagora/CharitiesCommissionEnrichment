"""API routes."""
from fastapi import APIRouter

from app.api import auth, batches, charity, entities, exports, health

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(batches.router, prefix="/batches", tags=["Batches"])
api_router.include_router(entities.router, prefix="/entities", tags=["Entities"])
api_router.include_router(exports.router, prefix="/exports", tags=["Exports"])
api_router.include_router(charity.router, prefix="/charity", tags=["Charity"])
