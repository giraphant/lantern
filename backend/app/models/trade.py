"""
Trade history model.
"""
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Trade(Base):
    """Trade execution records."""

    __tablename__ = "trades"

    id = Column(String, primary_key=True)
    strategy_id = Column(String, ForeignKey("strategies.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Trade details
    exchange = Column(String, nullable=False)
    side = Column(String, nullable=False)  # buy, sell
    symbol = Column(String, nullable=False)
    quantity = Column(Numeric(precision=20, scale=10), nullable=False)
    price = Column(Numeric(precision=20, scale=10), nullable=False)

    # Action context
    action = Column(String, nullable=False)  # build, winddown

    # Relationship
    strategy = relationship("Strategy", back_populates="trades")
