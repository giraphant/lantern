"""
Strategy model - represents a funding rate arbitrage strategy.
"""
from datetime import datetime
from sqlalchemy import Column, String, Numeric, Integer, DateTime
from sqlalchemy.orm import relationship

from app.database import Base


class Strategy(Base):
    """Strategy configuration and status."""

    __tablename__ = "strategies"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

    # Exchange configuration
    exchange_a = Column(String, nullable=False)  # GRVT, Binance, etc.
    exchange_b = Column(String, nullable=False)  # Lighter, Backpack, etc.
    symbol = Column(String, nullable=False)  # BTC, ETH, etc.

    # Trading parameters
    size = Column(Numeric(precision=20, scale=10), nullable=False)
    max_position = Column(Numeric(precision=20, scale=10), nullable=False)

    # Threshold parameters
    build_threshold_apr = Column(Numeric(precision=10, scale=6), nullable=False)
    close_threshold_apr = Column(Numeric(precision=10, scale=6), nullable=False)

    # Execution parameters
    check_interval = Column(Integer, nullable=False)  # seconds

    # Status
    status = Column(String, nullable=False)  # running, stopped, error

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    funding_rates = relationship("FundingRateHistory", back_populates="strategy", cascade="all, delete-orphan")
    positions = relationship("PositionHistory", back_populates="strategy", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="strategy", cascade="all, delete-orphan")
