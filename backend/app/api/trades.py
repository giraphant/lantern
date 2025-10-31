"""
Trade history API endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import Trade

router = APIRouter()


@router.get("/", response_model=list[Trade])
async def get_all_trades(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get all trades across all strategies."""
    # TODO: Implement
    return []


@router.get("/{strategy_id}", response_model=list[Trade])
async def get_strategy_trades(
    strategy_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get trades for a specific strategy."""
    # TODO: Implement
    return []
