"""
Data recorder service - saves strategy data to database.
"""
from datetime import datetime
from decimal import Decimal
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.models import FundingRateHistory, PositionHistory, Trade

logger = logging.getLogger(__name__)


def get_websocket_manager():
    """Get WebSocket manager (lazy import to avoid circular dependency)."""
    from app.api.websocket import manager
    return manager


class DataRecorder:
    """Records strategy data to database."""

    def __init__(self, session_maker: async_sessionmaker):
        self.session_maker = session_maker

    async def record_funding_rate(
        self,
        strategy_id: str,
        exchange_a_rate: Decimal,
        exchange_b_rate: Decimal,
        spread: Decimal,
        spread_apr: Decimal
    ):
        """Record funding rate snapshot."""
        async with self.session_maker() as session:
            try:
                snapshot = FundingRateHistory(
                    timestamp=datetime.utcnow(),
                    strategy_id=strategy_id,
                    exchange_a_rate=exchange_a_rate,
                    exchange_b_rate=exchange_b_rate,
                    spread=spread,
                    spread_apr=spread_apr
                )

                session.add(snapshot)
                await session.commit()

                logger.debug(f"Recorded funding rate for {strategy_id}")

                # Send WebSocket update
                ws_manager = get_websocket_manager()
                await ws_manager.send_funding_rate_update(strategy_id, {
                    "exchange_a_rate": float(exchange_a_rate),
                    "exchange_b_rate": float(exchange_b_rate),
                    "spread": float(spread),
                    "spread_apr": float(spread_apr),
                    "timestamp": snapshot.timestamp.isoformat()
                })

            except Exception as e:
                logger.error(f"Error recording funding rate: {e}")
                await session.rollback()

    async def record_position(
        self,
        strategy_id: str,
        exchange_a_position: Decimal,
        exchange_b_position: Decimal,
        total_position: Decimal,
        unrealized_pnl: Decimal = None
    ):
        """Record position snapshot."""
        async with self.session_maker() as session:
            try:
                snapshot = PositionHistory(
                    timestamp=datetime.utcnow(),
                    strategy_id=strategy_id,
                    exchange_a_position=exchange_a_position,
                    exchange_b_position=exchange_b_position,
                    total_position=total_position,
                    unrealized_pnl=unrealized_pnl
                )

                session.add(snapshot)
                await session.commit()

                logger.debug(f"Recorded position for {strategy_id}")

                # Send WebSocket update
                ws_manager = get_websocket_manager()
                await ws_manager.send_position_update(strategy_id, {
                    "exchange_a_position": float(exchange_a_position),
                    "exchange_b_position": float(exchange_b_position),
                    "total_position": float(total_position),
                    "unrealized_pnl": float(unrealized_pnl) if unrealized_pnl else None,
                    "timestamp": snapshot.timestamp.isoformat()
                })

            except Exception as e:
                logger.error(f"Error recording position: {e}")
                await session.rollback()

    async def record_trade(
        self,
        trade_id: str,
        strategy_id: str,
        exchange: str,
        side: str,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        action: str
    ):
        """Record trade execution."""
        async with self.session_maker() as session:
            try:
                trade = Trade(
                    id=trade_id,
                    strategy_id=strategy_id,
                    timestamp=datetime.utcnow(),
                    exchange=exchange,
                    side=side,
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    action=action
                )

                session.add(trade)
                await session.commit()

                logger.info(f"Recorded trade {trade_id} for {strategy_id}")

            except Exception as e:
                logger.error(f"Error recording trade: {e}")
                await session.rollback()
