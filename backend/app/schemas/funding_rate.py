"""
Funding rate schemas.
"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class FundingRateSnapshot(BaseModel):
    """Historical funding rate snapshot."""
    timestamp: datetime
    strategy_id: str
    exchange_a_rate: Decimal
    exchange_b_rate: Decimal
    spread: Decimal
    spread_apr: Decimal

    class Config:
        from_attributes = True


class FundingRateCurrent(BaseModel):
    """Current funding rate for a strategy."""
    strategy_id: str
    strategy_name: str
    exchange_a: str
    exchange_b: str
    symbol: str
    exchange_a_rate: Decimal
    exchange_b_rate: Decimal
    spread: Decimal
    spread_apr: Decimal
    timestamp: datetime
