"""
Strategy execution manager - orchestrates running strategies.
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime
import logging

# Add src to path to import exchange clients
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from exchanges.grvt import GrvtClient
from exchanges.lighter import LighterClient
from exchanges.binance import BinanceClient
from exchanges.backpack import BackpackClient

logger = logging.getLogger(__name__)


class StrategyConfig:
    """Configuration object for strategy."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class StrategyExecutor:
    """Executes a single strategy."""

    def __init__(self, strategy_id: str, config: Dict):
        self.strategy_id = strategy_id
        self.config = config
        self.running = False
        self.task: Optional[asyncio.Task] = None

        # Exchange clients
        self.exchange_a = None
        self.exchange_b = None

        # Callbacks for data updates
        self.on_funding_rate_update = None
        self.on_position_update = None
        self.on_trade_executed = None

    def _init_exchange(self, exchange_type: str, symbol: str, size: Decimal):
        """Initialize exchange client."""
        exchange_type = exchange_type.upper()

        # Create config object
        cfg = StrategyConfig(
            ticker=symbol,
            quantity=size
        )

        if exchange_type == "GRVT":
            return GrvtClient(cfg)
        elif exchange_type == "LIGHTER":
            return LighterClient(cfg)
        elif exchange_type == "BINANCE":
            return BinanceClient(cfg)
        elif exchange_type == "BACKPACK":
            return BackpackClient(cfg)
        else:
            raise ValueError(f"Unsupported exchange: {exchange_type}")

    async def start(self):
        """Start strategy execution."""
        if self.running:
            logger.warning(f"Strategy {self.strategy_id} already running")
            return

        logger.info(f"Starting strategy {self.strategy_id}")

        # Initialize exchanges
        self.exchange_a = self._init_exchange(
            self.config['exchange_a'],
            self.config['symbol'],
            Decimal(str(self.config['size']))
        )
        self.exchange_b = self._init_exchange(
            self.config['exchange_b'],
            self.config['symbol'],
            Decimal(str(self.config['size']))
        )

        # Connect to exchanges
        await self.exchange_a.connect()
        await self.exchange_b.connect()

        # Start execution loop
        self.running = True
        self.task = asyncio.create_task(self._execution_loop())

        logger.info(f"Strategy {self.strategy_id} started")

    async def stop(self):
        """Stop strategy execution."""
        if not self.running:
            return

        logger.info(f"Stopping strategy {self.strategy_id}")

        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        # Disconnect exchanges
        if self.exchange_a:
            await self.exchange_a.disconnect()
        if self.exchange_b:
            await self.exchange_b.disconnect()

        logger.info(f"Strategy {self.strategy_id} stopped")

    async def _execution_loop(self):
        """Main execution loop."""
        check_interval = self.config.get('check_interval', 300)

        try:
            while self.running:
                try:
                    # Get funding rates
                    await self._check_funding_rates()

                    # Check positions
                    await self._check_positions()

                    # Wait before next check
                    await asyncio.sleep(check_interval)

                except Exception as e:
                    logger.error(f"Error in execution loop for {self.strategy_id}: {e}", exc_info=True)
                    await asyncio.sleep(check_interval)

        except asyncio.CancelledError:
            logger.info(f"Execution loop cancelled for {self.strategy_id}")

    async def _check_funding_rates(self):
        """Check and record funding rates."""
        try:
            # Get contract IDs
            contract_a = self.exchange_a.config.contract_id
            contract_b = self.exchange_b.config.contract_id

            # Get funding rates
            rate_a = await self.exchange_a.get_funding_rate(contract_a)
            rate_b = await self.exchange_b.get_funding_rate(contract_b)

            # Get intervals
            interval_a = await self.exchange_a.get_funding_interval_hours(contract_a)
            interval_b = await self.exchange_b.get_funding_interval_hours(contract_b)

            # Calculate spread (normalize to same interval if needed)
            spread = rate_a - rate_b

            # Calculate APR (using exchange A's interval as reference)
            spread_apr = spread * Decimal(24 / interval_a) * Decimal(365)

            # Callback to save data
            if self.on_funding_rate_update:
                await self.on_funding_rate_update(
                    strategy_id=self.strategy_id,
                    exchange_a_rate=rate_a,
                    exchange_b_rate=rate_b,
                    spread=spread,
                    spread_apr=spread_apr
                )

            logger.info(f"Strategy {self.strategy_id}: Spread {spread_apr*100:.2f}% APR")

        except Exception as e:
            logger.error(f"Error checking funding rates for {self.strategy_id}: {e}")

    async def _check_positions(self):
        """Check and record positions."""
        try:
            position_a = await self.exchange_a.get_positions()
            position_b = await self.exchange_b.get_positions()
            total_position = position_a + position_b

            # Callback to save data
            if self.on_position_update:
                await self.on_position_update(
                    strategy_id=self.strategy_id,
                    exchange_a_position=position_a,
                    exchange_b_position=position_b,
                    total_position=total_position
                )

            logger.debug(f"Strategy {self.strategy_id}: Positions A={position_a}, B={position_b}")

        except Exception as e:
            logger.error(f"Error checking positions for {self.strategy_id}: {e}")


class StrategyManager:
    """Manages multiple strategy executors."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.strategies: Dict[str, StrategyExecutor] = {}
        self._initialized = True

        logger.info("StrategyManager initialized")

    async def start_strategy(self, strategy_id: str, config: Dict):
        """Start a strategy."""
        if strategy_id in self.strategies:
            logger.warning(f"Strategy {strategy_id} already exists")
            return

        executor = StrategyExecutor(strategy_id, config)
        self.strategies[strategy_id] = executor

        await executor.start()

    async def stop_strategy(self, strategy_id: str):
        """Stop a strategy."""
        executor = self.strategies.get(strategy_id)
        if not executor:
            logger.warning(f"Strategy {strategy_id} not found")
            return

        await executor.stop()
        del self.strategies[strategy_id]

    def get_running_strategies(self) -> list:
        """Get list of running strategy IDs."""
        return [sid for sid, executor in self.strategies.items() if executor.running]

    def is_running(self, strategy_id: str) -> bool:
        """Check if strategy is running."""
        executor = self.strategies.get(strategy_id)
        return executor.running if executor else False


# Singleton instance
strategy_manager = StrategyManager()
