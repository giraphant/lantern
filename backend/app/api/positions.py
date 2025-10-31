"""
Position API endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import PositionSnapshot

router = APIRouter()


@router.get("/", response_model=list[PositionSnapshot])
async def get_current_positions(db: AsyncSession = Depends(get_db)):
    """Get current positions for all active strategies."""
    # TODO: Implement
    return []


@router.get("/{strategy_id}/history", response_model=list[PositionSnapshot])
async def get_position_history(
    strategy_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get historical positions for a strategy."""
    # TODO: Implement
    return []
