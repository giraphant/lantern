"""
Trade schemas.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel


class Trade(BaseModel):
    """Trade record."""
    id: str
    strategy_id: str
    timestamp: datetime
    exchange: str
    side: Literal["buy", "sell"]
    symbol: str
    quantity: Decimal
    price: Decimal
    action: Literal["build", "winddown"]

    class Config:
        from_attributes = True


class TradeList(BaseModel):
    """List of trades with pagination."""
    trades: list[Trade]
    total: int
    page: int
    page_size: int
