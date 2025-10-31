"""
Strategy schemas for API validation.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


class StrategyBase(BaseModel):
    """Base strategy fields."""
    name: str = Field(..., min_length=1, max_length=100)
    exchange_a: str = Field(..., description="Exchange A (e.g., GRVT, Binance)")
    exchange_b: str = Field(..., description="Exchange B (e.g., Lighter, Backpack)")
    symbol: str = Field(..., description="Trading symbol (e.g., BTC, ETH)")
    size: Decimal = Field(..., gt=0, description="Order size per trade")
    max_position: Decimal = Field(..., gt=0, description="Maximum position size")
    build_threshold_apr: Decimal = Field(..., description="APR threshold to start building (e.g., 0.05 = 5%)")
    close_threshold_apr: Decimal = Field(..., description="APR threshold to start closing (e.g., 0.02 = 2%)")
    check_interval: int = Field(default=300, ge=30, description="Check interval in seconds")


class StrategyCreate(StrategyBase):
    """Schema for creating a new strategy."""
    pass


class StrategyUpdate(BaseModel):
    """Schema for updating a strategy."""
    name: str | None = None
    size: Decimal | None = Field(None, gt=0)
    max_position: Decimal | None = Field(None, gt=0)
    build_threshold_apr: Decimal | None = None
    close_threshold_apr: Decimal | None = None
    check_interval: int | None = Field(None, ge=30)


class Strategy(StrategyBase):
    """Full strategy response."""
    id: str
    status: Literal["running", "stopped", "error"]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StrategyStatus(BaseModel):
    """Strategy status update."""
    status: Literal["running", "stopped", "error"]
