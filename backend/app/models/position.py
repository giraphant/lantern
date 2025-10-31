"""
Position history model.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class PositionHistory(Base):
    """Position snapshots over time."""

    __tablename__ = "position_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    strategy_id = Column(String, ForeignKey("strategies.id"), nullable=False, index=True)

    # Positions
    exchange_a_position = Column(Numeric(precision=20, scale=10), nullable=False)
    exchange_b_position = Column(Numeric(precision=20, scale=10), nullable=False)
    total_position = Column(Numeric(precision=20, scale=10), nullable=False)

    # PNL
    unrealized_pnl = Column(Numeric(precision=20, scale=10), nullable=True)

    # Relationship
    strategy = relationship("Strategy", back_populates="positions")
