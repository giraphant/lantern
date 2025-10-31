"""
Funding rate API endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import FundingRateSnapshot

router = APIRouter()


@router.get("/", response_model=list[FundingRateSnapshot])
async def get_current_funding_rates(db: AsyncSession = Depends(get_db)):
    """Get current funding rates for all active strategies."""
    # TODO: Implement
    return []


@router.get("/{strategy_id}/history", response_model=list[FundingRateSnapshot])
async def get_funding_rate_history(
    strategy_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get historical funding rates for a strategy."""
    # TODO: Implement
    return []
