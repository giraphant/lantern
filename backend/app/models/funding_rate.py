"""
Funding rate history model.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class FundingRateHistory(Base):
    """Funding rate snapshots over time."""

    __tablename__ = "funding_rate_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    strategy_id = Column(String, ForeignKey("strategies.id"), nullable=False, index=True)

    # Rates
    exchange_a_rate = Column(Numeric(precision=20, scale=10), nullable=False)
    exchange_b_rate = Column(Numeric(precision=20, scale=10), nullable=False)
    spread = Column(Numeric(precision=20, scale=10), nullable=False)
    spread_apr = Column(Numeric(precision=10, scale=6), nullable=False)

    # Relationship
    strategy = relationship("Strategy", back_populates="funding_rates")
