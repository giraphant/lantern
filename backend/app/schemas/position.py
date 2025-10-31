"""
Position schemas.
"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class PositionSnapshot(BaseModel):
    """Historical position snapshot."""
    timestamp: datetime
    strategy_id: str
    exchange_a_position: Decimal
    exchange_b_position: Decimal
    total_position: Decimal
    unrealized_pnl: Decimal | None

    class Config:
        from_attributes = True


class PositionCurrent(BaseModel):
    """Current position for a strategy."""
    strategy_id: str
    strategy_name: str
    exchange_a: str
    exchange_b: str
    symbol: str
    exchange_a_position: Decimal
    exchange_b_position: Decimal
    total_position: Decimal
    unrealized_pnl: Decimal | None
    timestamp: datetime
